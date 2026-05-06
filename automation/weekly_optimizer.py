#!/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/venv/bin/python3
"""
Weekly performance optimizer.
Fetches YouTube Analytics, analyzes with Claude Code, applies safe changes.
"""

import json
import subprocess
import sys
import re
from pathlib import Path
from datetime import datetime, timedelta
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Import change guardian and cleanup
sys.path.insert(0, str(Path(__file__).parent))
from change_guardian import ChangeGuardian
from youtube_scopes import SCOPES
from cleanup_old_runs import cleanup_old_runs
from ab_test_manager import advance_week as advance_ab_tests


def get_authenticated_service(api_name, api_version):
    """Authenticate and return API service."""
    creds = None
    token_path = Path('config/youtube_token.pickle')
    creds_path = Path('config/youtube_credentials.json')

    if token_path.exists():
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    return build(api_name, api_version, credentials=creds)


def sanitize_text(text, max_length=500):
    """Remove prompt injection patterns."""
    dangerous_patterns = [
        r"ignore\s+(previous|above|all)\s+instructions",
        r"system\s*:",
        r"you\s+are\s+now",
        r"forget\s+(everything|all|previous)",
        r"new\s+instructions",
        r"<script>",
        r"```",
        r"exec\(",
        r"eval\(",
    ]

    cleaned = text
    for pattern in dangerous_patterns:
        cleaned = re.sub(pattern, "[FILTERED]", cleaned, flags=re.IGNORECASE)

    return cleaned[:max_length]


def get_channel_videos(youtube, channel_id, days=7):
    """Get recent videos from channel."""
    since = (datetime.now() - timedelta(days=days)).isoformat() + 'Z'

    request = youtube.search().list(
        part='id,snippet',
        channelId=channel_id,
        maxResults=50,
        order='date',
        publishedAfter=since,
        type='video'
    )

    response = request.execute()

    videos = []
    for item in response.get('items', []):
        videos.append({
            'video_id': item['id']['videoId'],
            'title': sanitize_text(item['snippet']['title'], 100),
            'published_at': item['snippet']['publishedAt']
        })

    return videos


def get_video_analytics(analytics, video_ids):
    """Get analytics data for videos."""
    if not video_ids:
        return []

    video_ids_str = ','.join(video_ids)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=7)

    request = analytics.reports().query(
        ids='channel==MINE',
        startDate=start_date.isoformat(),
        endDate=end_date.isoformat(),
        metrics='views,estimatedMinutesWatched,likes,comments,shares,averageViewPercentage,subscribersGained,subscribersLost,engagedViews',
        dimensions='video',
        filters=f'video=={video_ids_str}'
    )

    response = request.execute()

    metrics = {}
    for row in response.get('rows', []):
        video_id = row[0]
        views = int(row[1])
        engaged_views = int(row[9]) if len(row) > 9 else views
        metrics[video_id] = {
            'views': views,
            'watch_time_minutes': int(row[2]),
            'likes': int(row[3]),
            'comments': int(row[4]),
            'shares': int(row[5]),
            'avg_retention': float(row[6]),
            'subscribers_gained': int(row[7]),
            'subscribers_lost': int(row[8]),
            'engaged_views': engaged_views,
            'engaged_view_rate': (engaged_views / views * 100) if views > 0 else 0.0,
        }

    return metrics


def _load_experiment_snapshot(run_dir: str) -> dict:
    """
    Load the experiment snapshot saved during video production.
    Returns a dict mapping config_key -> variant info, or empty dict.
    """
    snapshot_path = Path(run_dir) / "experiment_snapshot.json"
    if not snapshot_path.exists():
        return {}
    try:
        with open(snapshot_path) as f:
            return json.load(f).get("experiments", {})
    except (json.JSONDecodeError, IOError):
        return {}


def record_ab_test_results(metrics_data):
    """
    Record video performance into ALL active A/B experiments.

    Uses the experiment_snapshot.json saved during video production to
    attribute each video to the correct variant — even if the experiment
    has since advanced to a different week. This ensures results are
    never misattributed due to timing.

    Also records which variant of every OTHER concurrent experiment was
    active when the video was produced (confound tracking), so you can
    check for cross-experiment interference during analysis.
    """
    queue_path = Path("automation/youtube_upload_queue.json")
    if not queue_path.exists():
        return

    try:
        with open(queue_path) as f:
            queue_data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return

    # Build video_id -> metadata mapping from queue
    video_metadata = {}
    for entry in queue_data.get("queue", []):
        tone = entry.get("tone", "unknown")
        run_dir = entry.get("run_dir", "")
        snapshot = _load_experiment_snapshot(run_dir)
        for video_type, video_info in entry.get("videos", {}).items():
            vid = video_info.get("video_id")
            if vid:
                video_metadata[vid] = {
                    "tone": tone,
                    "run_dir": run_dir,
                    "experiment_snapshot": snapshot,
                }

    # Load experiments
    experiments_path = Path("automation/state/ab_experiments.json")
    if not experiments_path.exists():
        return

    try:
        with open(experiments_path) as f:
            exp_data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return

    # Collect all existing video IDs across both variants to avoid duplicates
    recorded_count = 0
    for exp in exp_data.get("experiments", []):
        if exp.get("status") != "active":
            continue

        config_key = exp.get("config_key", "")
        all_existing_ids = set()
        for variant_key in ("control", "treatment"):
            for v in exp["results"][variant_key].get("videos", []):
                all_existing_ids.add(v["video_id"])

        for vid, m in metrics_data.items():
            if vid in all_existing_ids:
                continue

            meta = video_metadata.get(vid, {})
            snapshot = meta.get("experiment_snapshot", {})

            # Determine which variant this video was produced under.
            # Prefer the production-time snapshot; fall back to current variant.
            if config_key in snapshot:
                variant = snapshot[config_key]["variant"]
            else:
                variant = exp.get("current_variant", "control")

            results = exp["results"][variant]
            views = m.get("views", 0)
            engagement = m.get("likes", 0) + m.get("comments", 0) + m.get("shares", 0)
            retention = m.get("avg_retention", 0)
            engaged_view_rate = m.get("engaged_view_rate", 0.0)
            subscribers_gained = m.get("subscribers_gained", 0)

            # Build confound metadata: variants of all OTHER experiments
            concurrent_variants = {
                key: info["variant"]
                for key, info in snapshot.items()
                if key != config_key
            }

            results["videos"].append({
                "video_id": vid,
                "views": views,
                "engagement": engagement,
                "retention": retention,
                "engaged_view_rate": engaged_view_rate,
                "subscribers_gained": subscribers_gained,
                "tone": meta.get("tone", "unknown"),
                "concurrent_experiments": concurrent_variants,
                "date": datetime.now().isoformat()
            })
            results["total_views"] += views
            results["total_engagement"] += engagement
            results["total_subscribers_gained"] = results.get("total_subscribers_gained", 0) + subscribers_gained

            video_count = len(results["videos"])
            results["avg_retention"] = (
                (results["avg_retention"] * (video_count - 1) + retention) / video_count
            )
            results["avg_engaged_view_rate"] = (
                (results.get("avg_engaged_view_rate", 0) * (video_count - 1) + engaged_view_rate) / video_count
            )
            recorded_count += 1

    if recorded_count > 0:
        with open(experiments_path, "w") as f:
            json.dump(exp_data, f, indent=2)
        print(f"  🧪 Recorded {recorded_count} video results into A/B experiments")


def save_analytics_history(metrics_data, report_date):
    """Persist weekly analytics data for historical trend analysis."""
    history_path = Path("automation/state/analytics_history.json")

    if history_path.exists():
        with open(history_path) as f:
            history = json.load(f)
    else:
        history = {"weeks": []}

    total_views = sum(m.get('views', 0) for m in metrics_data.values())
    total_engagement = sum(
        m.get('likes', 0) + m.get('comments', 0) + m.get('shares', 0)
        for m in metrics_data.values()
    )
    total_subs_gained = sum(m.get('subscribers_gained', 0) for m in metrics_data.values())
    total_subs_lost = sum(m.get('subscribers_lost', 0) for m in metrics_data.values())
    avg_retention = (
        sum(m.get('avg_retention', 0) for m in metrics_data.values()) / len(metrics_data)
        if metrics_data else 0
    )
    engagement_rate = (total_engagement / total_views * 100) if total_views > 0 else 0

    week_entry = {
        "date": report_date,
        "videos_analyzed": len(metrics_data),
        "total_views": total_views,
        "total_engagement": total_engagement,
        "engagement_rate": round(engagement_rate, 2),
        "avg_retention": round(avg_retention, 2),
        "subscribers_gained": total_subs_gained,
        "subscribers_lost": total_subs_lost,
        "net_subscribers": total_subs_gained - total_subs_lost,
        "per_video_metrics": {
            vid: {
                "title": data.get("title", ""),
                "views": data.get("views", 0),
                "avg_retention": data.get("avg_retention", 0),
                "engagement": data.get("likes", 0) + data.get("comments", 0) + data.get("shares", 0)
            }
            for vid, data in metrics_data.items()
        }
    }

    history["weeks"].append(week_entry)

    with open(history_path, 'w') as f:
        json.dump(history, f, indent=2)

    return week_entry


def load_config():
    """Load configs."""
    with open('automation/config/automation_config.json') as f:
        automation_config = json.load(f)

    with open('config/config.json') as f:
        video_config = json.load(f)

    return automation_config, video_config


def analyze_with_claude(metrics_data, current_config):
    """Analyze metrics with Claude Code CLI."""
    prompt = f"""Analyze this week's educational video performance and suggest 1-2 optimizations.

METRICS:
{json.dumps(metrics_data, indent=2)}

CURRENT CONFIG:
- Video duration: {current_config['video_settings']['duration']}s
- Media items: {current_config['pipeline_settings']['min_media_items']}-{current_config['pipeline_settings']['max_media_items']}
- Current tone examples from recent videos

RULES:
1. Focus on engagement metrics (watch time, likes, shares, retention)
2. Suggest ONLY changes within safe ranges:
   - Duration: 15-120 seconds
   - Media items: 5-30
   - Tone: Any educational style (no profanity)
3. The "change" field MUST be one of these exact standardized strings:
   - "video_duration" for duration changes
   - "max_media_items" for max media item changes
   - "min_media_items" for min media item changes
   - "tone" for tone changes
   - "posting_time" for scheduling changes
   Do NOT use free-form descriptions. Use ONLY the strings listed above.
4. Output JSON ONLY with this exact schema:
{{
  "insights": ["insight 1", "insight 2"],
  "recommendations": [
    {{
      "change": "video_duration|max_media_items|min_media_items|tone|posting_time",
      "current_value": current_value,
      "proposed_value": proposed_value,
      "rationale": "why this change",
      "confidence": 0.85,
      "expected_impact": "what we expect to improve"
    }}
  ]
}}

Respond with ONLY valid JSON, no markdown or explanation:"""

    result = subprocess.run(
        ["/Users/ethantrokie/.local/bin/claude", "-p", prompt, "--model", "claude-sonnet-4-6", "--dangerously-skip-permissions"],
        capture_output=True,
        text=True,
        timeout=60
    )

    if result.returncode != 0:
        raise Exception(f"Claude CLI failed: {result.stderr}")

    # Parse JSON from output
    output = result.stdout.strip()

    # Try to extract JSON from markdown code blocks if present
    if "```json" in output:
        output = output.split("```json")[1].split("```")[0].strip()
    elif "```" in output:
        output = output.split("```")[1].split("```")[0].strip()

    return json.loads(output)


def apply_changes(auto_apply_changes, video_config):
    """Apply validated changes to config."""
    changes_made = []

    for change in auto_apply_changes:
        change_type = change["change"].lower()
        proposed_value = change["proposed_value"]

        if "duration" in change_type:
            video_config["video_settings"]["duration"] = proposed_value
            changes_made.append(f"video_duration: {change['current_value']} → {proposed_value}")

        elif "max_media" in change_type or "media" in change_type and "max" in str(proposed_value):
            video_config["pipeline_settings"]["max_media_items"] = proposed_value
            changes_made.append(f"max_media_items: {change['current_value']} → {proposed_value}")

        elif "min_media" in change_type:
            video_config["pipeline_settings"]["min_media_items"] = proposed_value
            changes_made.append(f"min_media_items: {change['current_value']} → {proposed_value}")

    # Save updated config
    with open('config/config.json', 'w') as f:
        json.dump(video_config, f, indent=2)

    return changes_made


def save_optimization_state(changes, analysis):
    """Save optimization state for tracking."""
    state_file = Path("automation/state/optimization_state.json")

    with open(state_file) as f:
        state = json.load(f)

    for change_desc in changes:
        parts = change_desc.split(": ")
        if len(parts) == 2:
            change_type, values = parts
            from_val, to_val = values.split(" → ")

            state["optimizations"].append({
                "date": datetime.now().isoformat(),
                "change": change_type,
                "from": from_val,
                "to": to_val,
                "rationale": analysis.get("insights", [""])[0],
                "impact_observed": None
            })

    state["last_analysis"] = datetime.now().isoformat()

    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)


def generate_report(metrics_data, analysis, validation_results, changes_applied):
    """Generate markdown report."""
    report_date = datetime.now().strftime('%Y-%m-%d')
    report_path = Path(f"automation/reports/{report_date}-analysis.md")

    # Calculate totals
    total_views = sum(m.get('views', 0) for m in metrics_data.values())
    total_engagement = sum(m.get('likes', 0) + m.get('comments', 0) + m.get('shares', 0)
                          for m in metrics_data.values())

    report = f"""# Weekly Performance Analysis - {report_date}

## Summary
- Videos analyzed: {len(metrics_data)}
- Total views: {total_views:,}
- Total engagement: {total_engagement} (likes + comments + shares)

## Insights
{chr(10).join(f'- {insight}' for insight in analysis.get('insights', []))}

## Recommendations

### Auto-Applied (High Confidence)
{chr(10).join(f'- {change}' for change in changes_applied) if changes_applied else '- None this week'}

### Pending Review (Medium Confidence)
{chr(10).join(f'- {rec["change"]}: {rec["rationale"]} (confidence: {rec["confidence"]})'
              for rec in validation_results['needs_review']) if validation_results['needs_review'] else '- None this week'}

### Rejected
{chr(10).join(f'- {rec["change"]}: {rec["validation_reason"]}'
              for rec in validation_results['rejected']) if validation_results['rejected'] else '- None'}

## Changes Applied
{chr(10).join(f'- {change}' for change in changes_applied) if changes_applied else '- No changes applied this week'}

## Next Week Focus
- Monitor impact of applied changes
- Continue tracking retention metrics
"""

    with open(report_path, 'w') as f:
        f.write(report)

    return report_path


def send_notification(report_path, changes_applied, pending_count):
    """Send iMessage notification."""
    message = f"""📊 Weekly analysis complete!
Report: {report_path}
Changes: {len(changes_applied)} auto-applied, {pending_count} pending review"""

    subprocess.run(
        ["./automation/notification_helper.sh", message],
        check=True
    )


def main():
    """Main execution."""
    print("📊 Weekly Performance Optimizer")
    print("=" * 50)

    # Cleanup old runs (2 weeks retention)
    print("\n🧹 Cleaning up old pipeline runs...")
    deleted_count, freed_mb, errors = cleanup_old_runs(runs_dir="outputs/runs", days_to_keep=14, dry_run=False)

    if deleted_count > 0:
        print(f"   ✓ Deleted {deleted_count} old runs, freed {freed_mb:.1f} MB")
    else:
        print("   ✓ No old runs to clean up")

    if errors:
        print(f"   ⚠️  {len(errors)} errors occurred during cleanup")

    # Advance A/B test experiments (date-based, resilient to missed runs)
    print("\n🧪 Syncing A/B test experiments...")
    try:
        advance_ab_tests()
    except Exception as e:
        print(f"   ⚠️  A/B test sync failed (non-fatal): {e}")

    print()

    # Load configs
    automation_config, video_config = load_config()

    # Authenticate APIs
    print("Authenticating with YouTube...")
    youtube = get_authenticated_service('youtube', 'v3')
    analytics = get_authenticated_service('youtubeAnalytics', 'v2')

    # Get channel info
    print("Fetching channel info...")
    channels = youtube.channels().list(part='id', mine=True).execute()
    channel_id = channels['items'][0]['id']

    # Get recent videos
    print("Fetching recent videos...")
    videos = get_channel_videos(youtube, channel_id, days=7)
    print(f"  Found {len(videos)} videos")

    if not videos:
        print("No videos to analyze this week")
        return

    # Get analytics
    print("Fetching analytics data...")
    video_ids = [v['video_id'] for v in videos]
    metrics = get_video_analytics(analytics, video_ids)

    # Combine video info with metrics
    metrics_data = {}
    for video in videos:
        vid = video['video_id']
        if vid in metrics:
            metrics_data[vid] = {
                'title': video['title'],
                **metrics[vid]
            }

    # Record video results into active A/B experiments
    print("Recording A/B experiment results...")
    try:
        record_ab_test_results(metrics_data)
    except Exception as e:
        print(f"  ⚠️  A/B result recording failed (non-fatal): {e}")

    # Analyze with Claude
    print("Analyzing performance with Claude Code...")
    analysis = analyze_with_claude(metrics_data, video_config)

    print(f"  Insights: {len(analysis.get('insights', []))}")
    print(f"  Recommendations: {len(analysis.get('recommendations', []))}")

    # Validate changes
    print("Validating recommendations...")
    guardian = ChangeGuardian()
    validation_results = guardian.validate_all(analysis.get('recommendations', []))

    print(f"  Auto-apply: {len(validation_results['auto_apply'])}")
    print(f"  Needs review: {len(validation_results['needs_review'])}")
    print(f"  Rejected: {len(validation_results['rejected'])}")

    # Apply safe changes if enabled
    changes_applied = []
    if automation_config['optimization']['enabled']:
        if automation_config['optimization']['auto_apply_high_confidence']:
            print("Applying high-confidence changes...")
            changes_applied = apply_changes(validation_results['auto_apply'], video_config)

            for change in changes_applied:
                print(f"  ✓ Applied: {change}")

    # Save pending changes if any
    if validation_results['needs_review']:
        pending_path = Path("automation/pending_changes.json")
        with open(pending_path, 'w') as f:
            json.dump(validation_results['needs_review'], f, indent=2)
        print(f"  ⚠️  Pending changes saved to {pending_path}")

    # Update optimization state
    save_optimization_state(changes_applied, analysis)

    # Save analytics history for trend analysis
    report_date = datetime.now().strftime('%Y-%m-%d')
    print("Saving analytics history...")
    week_summary = save_analytics_history(metrics_data, report_date)
    print(f"  Engagement rate: {week_summary['engagement_rate']}%")
    print(f"  Net subscribers: {week_summary['net_subscribers']:+d}")

    # Generate report
    print("Generating report...")
    report_path = generate_report(metrics_data, analysis, validation_results, changes_applied)
    print(f"  Report saved to {report_path}")

    # Send notification
    if automation_config['notifications']['notify_on_weekly_report']:
        print("Sending notification...")
        send_notification(report_path, changes_applied, len(validation_results['needs_review']))

    print("\n✅ Weekly optimization complete!")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
