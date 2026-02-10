#!/usr/bin/env python3
"""
YouTube Upload Queue Processor

Manages staggered video uploads over multiple days:
- Day 0: full + short_hook (uploaded immediately by pipeline)
- Day 1: short_educational (queued, uploaded at 8 AM)
- Day 2: short_intro (queued, uploaded at 8 AM)

Usage:
    --add: Add new entry to queue (called by pipeline.sh after Day 0 uploads)
    --process: Process pending uploads (called hourly by launchd)
    --dry-run: Show what would be uploaded without actually uploading
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Constants
QUEUE_FILE = Path(__file__).parent / "youtube_upload_queue.json"
CENTRAL_TZ = ZoneInfo("America/Chicago")
UPLOAD_HOUR = 8  # 8 AM Central
CLEANUP_DAYS = 7  # Remove entries older than 7 days


def load_queue() -> dict:
    """Load queue from JSON file."""
    if not QUEUE_FILE.exists():
        return {"queue": []}
    with open(QUEUE_FILE) as f:
        return json.load(f)


def save_queue(data: dict) -> None:
    """Save queue to JSON file."""
    with open(QUEUE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_now_central() -> datetime:
    """Get current time in Central timezone."""
    return datetime.now(CENTRAL_TZ)


def add_to_queue(run_dir: str, topic: str, full_id: str, hook_id: str) -> None:
    """
    Add new entry to queue with Day 0 videos marked as uploaded.
    Educational scheduled for Day 1, Intro for Day 2.
    """
    data = load_queue()
    now = get_now_central()
    run_id = Path(run_dir).name

    # Check for duplicate
    for entry in data["queue"]:
        if entry["run_id"] == run_id:
            print(f"  Entry already exists for run {run_id}, skipping")
            return

    # Calculate scheduled dates (8 AM Central on Day 1 and Day 2)
    day0_date = now.strftime("%Y-%m-%d")
    day1_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    day2_date = (now + timedelta(days=2)).strftime("%Y-%m-%d")

    entry = {
        "run_id": run_id,
        "run_dir": run_dir,
        "topic": topic,
        "created_at": now.isoformat(),
        "videos": {
            "full": {
                "status": "uploaded",
                "scheduled_date": day0_date,
                "uploaded_at": now.isoformat(),
                "video_id": full_id
            },
            "short_hook": {
                "status": "uploaded",
                "scheduled_date": day0_date,
                "uploaded_at": now.isoformat(),
                "video_id": hook_id
            },
            "short_educational": {
                "status": "pending",
                "scheduled_date": day1_date,
                "uploaded_at": None,
                "video_id": None
            },
            "short_intro": {
                "status": "pending",
                "scheduled_date": day2_date,
                "uploaded_at": None,
                "video_id": None
            }
        },
        "crosslink_status": "pending"
    }

    data["queue"].append(entry)
    save_queue(data)
    print(f"  Added to queue: {run_id}")
    print(f"    - Educational scheduled for: {day1_date} at {UPLOAD_HOUR}:00 AM Central")
    print(f"    - Intro scheduled for: {day2_date} at {UPLOAD_HOUR}:00 AM Central")


def upload_video(run_dir: str, video_type: str, dry_run: bool = False) -> str | None:
    """
    Upload a single video and return the video ID.
    Returns None on failure.
    """
    video_file = Path(run_dir) / f"{video_type}.mp4"
    if not video_file.exists():
        print(f"    Video file not found: {video_file}")
        return None

    if dry_run:
        print(f"    [DRY RUN] Would upload: {video_file}")
        return "dry-run-id"

    # Get config for privacy setting
    config_file = Path("automation/config/automation_config.json")
    privacy = "unlisted"
    channel = ""
    if config_file.exists():
        with open(config_file) as f:
            config = json.load(f)
            privacy = config.get("youtube", {}).get("privacy_status", "unlisted")
            channel = config.get("youtube", {}).get("channel_handle", "")

    # Build upload command
    run_timestamp = Path(run_dir).name
    cmd = ["./upload_to_youtube.sh", f"--run={run_timestamp}", f"--type={video_type}", f"--privacy={privacy}"]
    if channel:
        cmd.append(f"--channel={channel}")

    print(f"    Uploading {video_type}...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent.parent)
        if result.returncode != 0:
            print(f"    Upload failed: {result.stderr}")
            return None

        # Read video ID from saved file
        video_id_file = Path(run_dir) / f"video_id_{video_type}.txt"
        if video_id_file.exists():
            video_id = video_id_file.read_text().strip()
            print(f"    Uploaded: {video_id}")
            return video_id
        else:
            print(f"    Warning: Video ID file not found after upload")
            return None
    except Exception as e:
        print(f"    Upload error: {e}")
        return None


def run_crosslink(entry: dict, dry_run: bool = False) -> bool:
    """
    Run cross-linking for all videos in the entry.
    Returns True on success.
    """
    videos = entry["videos"]
    full_id = videos["full"]["video_id"]
    hook_id = videos["short_hook"]["video_id"]
    edu_id = videos["short_educational"]["video_id"]
    intro_id = videos["short_intro"]["video_id"]

    if not all([full_id, hook_id, edu_id, intro_id]):
        print("    Cannot crosslink: missing video IDs")
        return False

    if dry_run:
        print(f"    [DRY RUN] Would crosslink: {full_id}, {hook_id}, {edu_id}, {intro_id}")
        return True

    # Set OUTPUT_DIR for crosslink script
    env = os.environ.copy()
    env["OUTPUT_DIR"] = entry["run_dir"]

    cmd = ["python3", "agents/crosslink_videos.py", full_id, hook_id, edu_id, intro_id]
    print(f"    Running crosslink...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent.parent, env=env)
        if result.returncode != 0:
            print(f"    Crosslink failed: {result.stderr}")
            return False
        print("    Crosslink complete")
        return True
    except Exception as e:
        print(f"    Crosslink error: {e}")
        return False


def process_queue(dry_run: bool = False) -> None:
    """
    Process pending uploads. Uploads videos scheduled for today at 8 AM or earlier.
    """
    data = load_queue()
    now = get_now_central()
    today = now.strftime("%Y-%m-%d")
    current_hour = now.hour

    print(f"Processing queue at {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"  Queue entries: {len(data['queue'])}")

    if not data["queue"]:
        print("  Queue is empty")
        return

    modified = False
    for entry in data["queue"]:
        run_id = entry["run_id"]
        run_dir = entry["run_dir"]

        # Check if run directory still exists
        if not Path(run_dir).exists():
            print(f"\n  [{run_id}] Run directory missing, skipping")
            continue

        print(f"\n  [{run_id}] {entry['topic']}")

        # Process each pending video
        for video_type in ["short_educational", "short_intro"]:
            video = entry["videos"][video_type]
            if video["status"] != "pending":
                continue

            scheduled = video["scheduled_date"]

            # Check if scheduled date has arrived
            if scheduled > today:
                print(f"    {video_type}: scheduled for {scheduled} (not yet)")
                continue

            # Check if it's past 8 AM (or if scheduled date is in the past)
            if scheduled < today or current_hour >= UPLOAD_HOUR:
                print(f"    {video_type}: ready to upload (scheduled {scheduled})")
                video_id = upload_video(run_dir, video_type, dry_run)
                if video_id:
                    video["status"] = "uploaded"
                    video["uploaded_at"] = now.isoformat()
                    video["video_id"] = video_id
                    modified = True
                else:
                    print(f"    {video_type}: upload failed, will retry next hour")
            else:
                print(f"    {video_type}: scheduled for {UPLOAD_HOUR}:00 AM today (current: {current_hour}:00)")

        # Check if all videos are uploaded and crosslink is pending
        all_uploaded = all(v["status"] == "uploaded" for v in entry["videos"].values())
        if all_uploaded and entry["crosslink_status"] == "pending":
            print(f"    All videos uploaded, running crosslink...")
            if run_crosslink(entry, dry_run):
                entry["crosslink_status"] = "completed"
                modified = True
            else:
                print(f"    Crosslink failed, will retry next hour")

    # Cleanup old completed entries
    cutoff = (now - timedelta(days=CLEANUP_DAYS)).isoformat()
    original_count = len(data["queue"])
    data["queue"] = [
        e for e in data["queue"]
        if e["crosslink_status"] != "completed" or e["created_at"] > cutoff
    ]
    if len(data["queue"]) < original_count:
        print(f"\n  Cleaned up {original_count - len(data['queue'])} old entries")
        modified = True

    if modified:
        save_queue(data)
        print("\n  Queue state saved")
    else:
        print("\n  No changes made")


def show_status() -> None:
    """Display current queue status."""
    data = load_queue()
    now = get_now_central()

    print(f"Queue Status ({now.strftime('%Y-%m-%d %H:%M %Z')})")
    print("=" * 60)

    if not data["queue"]:
        print("  Queue is empty")
        return

    for entry in data["queue"]:
        print(f"\n{entry['run_id']}: {entry['topic']}")
        print(f"  Created: {entry['created_at']}")
        for vtype, vdata in entry["videos"].items():
            status_icon = "" if vdata["status"] == "uploaded" else ""
            print(f"  {status_icon} {vtype}: {vdata['status']} (scheduled: {vdata['scheduled_date']})")
        crosslink_icon = "" if entry["crosslink_status"] == "completed" else ""
        print(f"  {crosslink_icon} Crosslink: {entry['crosslink_status']}")


def main():
    parser = argparse.ArgumentParser(description="YouTube Upload Queue Processor")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add entry to queue")
    add_parser.add_argument("--run-dir", required=True, help="Run directory path")
    add_parser.add_argument("--topic", required=True, help="Video topic/title")
    add_parser.add_argument("--full-id", required=True, help="Full video YouTube ID")
    add_parser.add_argument("--hook-id", required=True, help="Hook short YouTube ID")

    # Process command
    process_parser = subparsers.add_parser("process", help="Process pending uploads")
    process_parser.add_argument("--dry-run", action="store_true", help="Show what would be done without doing it")

    # Status command
    subparsers.add_parser("status", help="Show queue status")

    # Legacy argument style support (for backward compatibility with plan)
    parser.add_argument("--add", action="store_true", help="(legacy) Add mode")
    parser.add_argument("--process", action="store_true", help="(legacy) Process mode")
    parser.add_argument("--dry-run", action="store_true", help="(legacy) Dry run")
    parser.add_argument("--run-dir", help="(legacy) Run directory")
    parser.add_argument("--topic", help="(legacy) Topic")
    parser.add_argument("--full-id", help="(legacy) Full video ID")
    parser.add_argument("--hook-id", help="(legacy) Hook video ID")

    args = parser.parse_args()

    # Handle legacy argument style
    if args.add:
        if not all([args.run_dir, args.topic, args.full_id, args.hook_id]):
            print("Error: --add requires --run-dir, --topic, --full-id, --hook-id")
            sys.exit(1)
        add_to_queue(args.run_dir, args.topic, args.full_id, args.hook_id)
    elif args.process:
        process_queue(args.dry_run)
    elif args.command == "add":
        add_to_queue(args.run_dir, args.topic, args.full_id, args.hook_id)
    elif args.command == "process":
        process_queue(args.dry_run)
    elif args.command == "status":
        show_status()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
