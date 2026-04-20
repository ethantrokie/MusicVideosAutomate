#!/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/venv/bin/python3
"""
One-time backfill: pull lifetime analytics for ALL videos in the upload queue.

Writes results to automation/state/video_performance_history.json with per-video
metrics joined to topic, format, and category metadata.

Usage:
    ./venv/bin/python3 automation/backfill_analytics.py

Note: Uses pickle for YouTube API token storage (matching existing weekly_optimizer.py
pattern). The pickle file is locally-generated auth credentials, not untrusted input.
"""

import json
import sys
import pickle  # noqa: S403 — loading locally-generated YouTube API credentials
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

sys.path.insert(0, str(Path(__file__).parent))
from youtube_scopes import SCOPES


def get_authenticated_service(api_name, api_version):
    """Authenticate and return API service."""
    creds = None
    token_path = Path('config/youtube_token.pickle')
    creds_path = Path('config/youtube_credentials.json')

    if token_path.exists():
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)  # noqa: S301 — trusted local credentials

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


def fetch_analytics_batch(analytics, video_ids, start_date, end_date):
    """Fetch analytics for a batch of video IDs (max ~200 per request)."""
    if not video_ids:
        return {}

    video_ids_str = ','.join(video_ids)

    request = analytics.reports().query(
        ids='channel==MINE',
        startDate=start_date,
        endDate=end_date,
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


CATEGORY_KEYWORDS = {
    'metalworking': ['laser cut', 'metal', 'forging', 'forge', 'welding', 'weld', 'plasma cut', 'cnc', 'milling'],
    'manufacturing': ['grain', 'paper', 'wood', 'injection mold', 'extrusion', 'extrud', 'chocolate',
                       'fiberglass', 'anodiz', 'tempered glass', 'ball bearing', 'bearing'],
    'electrical_engineering': ['motor', 'transformer', 'diode', 'circuit', 'kirchhoff', 'piezoelectric',
                                'voltage', 'induction motor', 'regenerative brak'],
    'mechanical_engineering': ['engine', 'turbofan', 'hydraulic', 'pneumatic', 'excavator'],
    'food_science': ['freeze-dry', 'freeze dry', 'chocolate', 'snap'],
    'chemistry': ['chemical vapor', 'anodiz', 'sewage'],
    'biology': ['kidney', 'urine', 'eye focus', 'human eye'],
    'computer_science': ['sql', 'hash table', 'microchip', 'database'],
    'physics': ['sonar', 'polarized', 'sunglasses', 'light'],
    'environmental': ['water purif', 'sewage'],
}


def categorize_topic(topic):
    """Assign a category to a topic string."""
    topic_lower = topic.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in topic_lower for kw in keywords):
            return category
    return 'other'


def main():
    print("=== Backfill: Pulling lifetime analytics for all uploaded videos ===\n")

    # Load upload queue
    queue_path = Path("automation/youtube_upload_queue.json")
    if not queue_path.exists():
        print("No upload queue found.")
        return

    with open(queue_path) as f:
        queue_data = json.load(f)

    # Build video_id -> metadata mapping
    video_metadata = {}
    for entry in queue_data.get("queue", []):
        topic = entry.get("topic", "Unknown")
        created_at = entry.get("created_at", "")
        tone = entry.get("tone", "unknown")
        run_id = entry.get("run_id", "")
        for fmt, info in entry.get("videos", {}).items():
            vid = info.get("video_id")
            if vid:
                video_metadata[vid] = {
                    "topic": topic,
                    "format": fmt,
                    "created_at": created_at,
                    "tone": tone,
                    "run_id": run_id,
                    "category": categorize_topic(topic),
                }

    all_video_ids = list(video_metadata.keys())
    print(f"Found {len(all_video_ids)} videos across {len(queue_data['queue'])} production runs")

    # Authenticate
    print("Authenticating with YouTube Analytics API...")
    analytics = get_authenticated_service('youtubeAnalytics', 'v2')

    # Fetch lifetime analytics — use the earliest upload date to now
    dates = []
    for entry in queue_data.get("queue", []):
        ca = entry.get("created_at", "")
        if ca:
            try:
                dates.append(datetime.fromisoformat(ca).date())
            except ValueError:
                pass

    start_date = (min(dates) - timedelta(days=1)).isoformat() if dates else "2026-01-01"
    end_date = datetime.now().date().isoformat()
    print(f"Date range: {start_date} to {end_date}")

    # Fetch in batches of 100 (API limit for filters)
    all_metrics = {}
    batch_size = 100
    for i in range(0, len(all_video_ids), batch_size):
        batch = all_video_ids[i:i + batch_size]
        print(f"  Fetching batch {i // batch_size + 1} ({len(batch)} videos)...")
        batch_metrics = fetch_analytics_batch(analytics, batch, start_date, end_date)
        all_metrics.update(batch_metrics)

    print(f"\nGot analytics for {len(all_metrics)} / {len(all_video_ids)} videos")

    # Join metrics with metadata
    videos = []
    for vid, meta in video_metadata.items():
        m = all_metrics.get(vid, {})
        videos.append({
            "video_id": vid,
            "topic": meta["topic"],
            "format": meta["format"],
            "category": meta["category"],
            "tone": meta["tone"],
            "created_at": meta["created_at"],
            "run_id": meta["run_id"],
            "views": m.get("views", 0),
            "engaged_views": m.get("engaged_views", 0),
            "engaged_view_rate": m.get("engaged_view_rate", 0.0),
            "avg_retention": m.get("avg_retention", 0.0),
            "likes": m.get("likes", 0),
            "comments": m.get("comments", 0),
            "shares": m.get("shares", 0),
            "subscribers_gained": m.get("subscribers_gained", 0),
            "subscribers_lost": m.get("subscribers_lost", 0),
            "watch_time_minutes": m.get("watch_time_minutes", 0),
            "has_analytics": vid in all_metrics,
        })

    # Aggregate by topic
    topic_agg = defaultdict(lambda: {
        "views": 0, "engaged_views": 0, "retention_sum": 0.0, "retention_count": 0,
        "subs_gained": 0, "engagement": 0, "formats": [], "category": "other",
    })
    for v in videos:
        if not v["has_analytics"]:
            continue
        t = topic_agg[v["topic"]]
        t["views"] += v["views"]
        t["engaged_views"] += v["engaged_views"]
        t["retention_sum"] += v["avg_retention"]
        t["retention_count"] += 1
        t["subs_gained"] += v["subscribers_gained"]
        t["engagement"] += v["likes"] + v["comments"] + v["shares"]
        t["formats"].append(v["format"])
        t["category"] = v["category"]

    # Aggregate by category
    cat_agg = defaultdict(lambda: {
        "views": 0, "engaged_views": 0, "retention_sum": 0.0, "retention_count": 0,
        "subs_gained": 0, "engagement": 0, "topics": set(),
    })
    for topic, t in topic_agg.items():
        c = cat_agg[t["category"]]
        c["views"] += t["views"]
        c["engaged_views"] += t["engaged_views"]
        c["retention_sum"] += t["retention_sum"]
        c["retention_count"] += t["retention_count"]
        c["subs_gained"] += t["subs_gained"]
        c["engagement"] += t["engagement"]
        c["topics"].add(topic)

    # Aggregate by format
    format_agg = defaultdict(lambda: {
        "views": 0, "engaged_views": 0, "retention_sum": 0.0, "count": 0,
        "subs_gained": 0, "engagement": 0,
    })
    for v in videos:
        if not v["has_analytics"]:
            continue
        fa = format_agg[v["format"]]
        fa["views"] += v["views"]
        fa["engaged_views"] += v["engaged_views"]
        fa["retention_sum"] += v["avg_retention"]
        fa["count"] += 1
        fa["subs_gained"] += v["subscribers_gained"]
        fa["engagement"] += v["likes"] + v["comments"] + v["shares"]

    # Print reports
    print("\n" + "=" * 100)
    print("TOPIC PERFORMANCE (sorted by engaged view rate)")
    print("=" * 100)
    print(f"{'Topic':<55} {'Views':>7} {'EngRate':>8} {'AvgRet':>7} {'Subs':>5} {'Engage':>7} {'Vids':>5}")
    print("-" * 100)

    sorted_topics = sorted(
        topic_agg.items(),
        key=lambda x: (x[1]["engaged_views"] / max(x[1]["views"], 1) * 100) if x[1]["views"] > 0 else 0,
        reverse=True
    )
    for topic, t in sorted_topics:
        avg_ret = t["retention_sum"] / t["retention_count"] if t["retention_count"] else 0
        eng_rate = (t["engaged_views"] / t["views"] * 100) if t["views"] > 0 else 0
        print(f"{topic:<55} {t['views']:>7} {eng_rate:>7.1f}% {avg_ret:>6.1f}% {t['subs_gained']:>5} {t['engagement']:>7} {t['retention_count']:>5}")

    print("\n" + "=" * 100)
    print("CATEGORY PERFORMANCE (sorted by engaged view rate)")
    print("=" * 100)
    print(f"{'Category':<25} {'Views':>8} {'EngRate':>8} {'AvgRet':>7} {'Subs':>5} {'Engage':>7} {'Topics':>7}")
    print("-" * 80)

    sorted_cats = sorted(
        cat_agg.items(),
        key=lambda x: (x[1]["engaged_views"] / max(x[1]["views"], 1) * 100) if x[1]["views"] > 0 else 0,
        reverse=True
    )
    for cat, c in sorted_cats:
        avg_ret = c["retention_sum"] / c["retention_count"] if c["retention_count"] else 0
        eng_rate = (c["engaged_views"] / c["views"] * 100) if c["views"] > 0 else 0
        print(f"{cat:<25} {c['views']:>8} {eng_rate:>7.1f}% {avg_ret:>6.1f}% {c['subs_gained']:>5} {c['engagement']:>7} {len(c['topics']):>7}")
        for t in sorted(c["topics"]):
            print(f"    {t}")

    print("\n" + "=" * 100)
    print("FORMAT PERFORMANCE")
    print("=" * 100)
    print(f"{'Format':<25} {'Views':>8} {'EngRate':>8} {'AvgRet':>7} {'Subs':>5} {'Engage':>7} {'Count':>6}")
    print("-" * 75)

    sorted_fmts = sorted(format_agg.items(), key=lambda x: x[1]["views"], reverse=True)
    for fmt, fa in sorted_fmts:
        avg_ret = fa["retention_sum"] / fa["count"] if fa["count"] else 0
        eng_rate = (fa["engaged_views"] / fa["views"] * 100) if fa["views"] > 0 else 0
        print(f"{fmt:<25} {fa['views']:>8} {eng_rate:>7.1f}% {avg_ret:>6.1f}% {fa['subs_gained']:>5} {fa['engagement']:>7} {fa['count']:>6}")

    # Save everything
    output = {
        "backfill_date": datetime.now().isoformat(),
        "date_range": {"start": start_date, "end": end_date},
        "total_videos": len(all_video_ids),
        "videos_with_analytics": len(all_metrics),
        "videos": videos,
        "topic_summary": {
            topic: {
                "category": t["category"],
                "total_views": t["views"],
                "total_engaged_views": t["engaged_views"],
                "engaged_view_rate": round((t["engaged_views"] / t["views"] * 100) if t["views"] > 0 else 0, 1),
                "avg_retention": round(t["retention_sum"] / t["retention_count"], 1) if t["retention_count"] else 0,
                "subscribers_gained": t["subs_gained"],
                "total_engagement": t["engagement"],
                "video_count": t["retention_count"],
            }
            for topic, t in sorted_topics
        },
        "category_summary": {
            cat: {
                "total_views": c["views"],
                "total_engaged_views": c["engaged_views"],
                "engaged_view_rate": round((c["engaged_views"] / c["views"] * 100) if c["views"] > 0 else 0, 1),
                "avg_retention": round(c["retention_sum"] / c["retention_count"], 1) if c["retention_count"] else 0,
                "subscribers_gained": c["subs_gained"],
                "total_engagement": c["engagement"],
                "topic_count": len(c["topics"]),
                "topics": sorted(c["topics"]),
            }
            for cat, c in sorted_cats
        },
        "format_summary": {
            fmt: {
                "total_views": fa["views"],
                "total_engaged_views": fa["engaged_views"],
                "engaged_view_rate": round((fa["engaged_views"] / fa["views"] * 100) if fa["views"] > 0 else 0, 1),
                "avg_retention": round(fa["retention_sum"] / fa["count"], 1) if fa["count"] else 0,
                "subscribers_gained": fa["subs_gained"],
                "total_engagement": fa["engagement"],
                "video_count": fa["count"],
            }
            for fmt, fa in sorted_fmts
        },
    }

    output_path = Path("automation/state/video_performance_history.json")
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved full results to {output_path}")
    print("Done!")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
