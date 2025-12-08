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

# Import change guardian
sys.path.insert(0, str(Path(__file__).parent))
from change_guardian import ChangeGuardian
from youtube_scopes import SCOPES


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
        metrics='views,estimatedMinutesWatched,likes,comments,shares,averageViewPercentage',
        dimensions='video',
        filters=f'video=={video_ids_str}'
    )

    response = request.execute()

    metrics = {}
    for row in response.get('rows', []):
        video_id = row[0]
        metrics[video_id] = {
            'views': int(row[1]),
            'watch_time_minutes': int(row[2]),
            'likes': int(row[3]),
            'comments': int(row[4]),
            'shares': int(row[5]),
            'avg_retention': float(row[6])
        }

    return metrics


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
3. Output JSON ONLY with this exact schema:
{{
  "insights": ["insight 1", "insight 2"],
  "recommendations": [
    {{
      "change": "description of what to change",
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
        ["/Users/ethantrokie/.npm-global/bin/claude", "-p", prompt, "--model", "claude-sonnet-4-5", "--dangerously-skip-permissions"],
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
