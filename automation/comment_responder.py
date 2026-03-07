#!/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/venv/bin/python3
"""
Comment Responder Bot - Fetches new YouTube comments and posts AI-generated
educational replies to build community engagement.
"""

import json
import subprocess
import sys
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from youtube_channel_helper import get_authenticated_service


def get_recent_comments(youtube, channel_id, max_results=20):
    """Fetch recent comments on channel videos."""
    request = youtube.commentThreads().list(
        part="snippet",
        allThreadsRelatedToChannelId=channel_id,
        maxResults=max_results,
        order="time",
        textFormat="plainText"
    )
    response = request.execute()

    comments = []
    for item in response.get("items", []):
        snippet = item["snippet"]["topLevelComment"]["snippet"]
        author_channel_id = snippet.get("authorChannelId", {}).get("value", "")
        comments.append({
            "comment_id": item["snippet"]["topLevelComment"]["id"],
            "thread_id": item["id"],
            "video_id": snippet["videoId"],
            "author": snippet["authorDisplayName"],
            "author_channel_id": author_channel_id,
            "text": snippet["textDisplay"],
            "published_at": snippet["publishedAt"],
            "reply_count": item["snippet"]["totalReplyCount"]
        })

    return comments


def has_channel_reply(youtube, thread_id, channel_id):
    """Check if the channel has already replied to this comment thread."""
    request = youtube.comments().list(
        part="snippet",
        parentId=thread_id,
        maxResults=20,
        textFormat="plainText"
    )
    response = request.execute()

    for item in response.get("items", []):
        if item["snippet"]["authorChannelId"]["value"] == channel_id:
            return True
    return False


def generate_reply(comment_text, video_title):
    """Generate an educational reply using Claude."""
    prompt = f"""You are a friendly science educator running the YouTube channel "Learning Science Music".
A viewer commented on your video "{video_title}".

Their comment: "{comment_text}"

Write a SHORT, friendly reply (1-3 sentences max) that:
1. Thanks them or acknowledges their comment
2. Adds one interesting related fact if relevant
3. Asks what topic they'd like to see next (only sometimes, not every reply)

Keep it conversational and warm. Do NOT use emojis excessively (1 max). Do NOT be corporate.
Output ONLY the reply text, nothing else."""

    result = subprocess.run(
        ["/Users/ethantrokie/.local/bin/claude", "-p", prompt, "--model", "claude-haiku-4-5-20251001", "--dangerously-skip-permissions"],
        capture_output=True,
        text=True,
        timeout=30
    )

    if result.returncode != 0:
        return None

    return result.stdout.strip()


def post_reply(youtube, thread_id, reply_text):
    """Post a reply to a comment thread."""
    request = youtube.comments().insert(
        part="snippet",
        body={
            "snippet": {
                "parentId": thread_id,
                "textOriginal": reply_text
            }
        }
    )
    return request.execute()


def get_video_title(youtube, video_id):
    """Get the title of a video."""
    request = youtube.videos().list(
        part="snippet",
        id=video_id
    )
    response = request.execute()
    items = response.get("items", [])
    if items:
        return items[0]["snippet"]["title"]
    return "Unknown Video"


def load_responded_comments():
    """Load list of already-responded comment IDs."""
    path = Path("automation/state/responded_comments.json")
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"responded": []}


def save_responded_comments(data):
    """Save responded comments list."""
    path = Path("automation/state/responded_comments.json")
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def process_comments(youtube, max_replies=5, dry_run=False):
    """Process recent comments and reply to unreplied ones."""
    # Get channel ID
    channels = youtube.channels().list(part='id', mine=True).execute()
    channel_id = channels['items'][0]['id']

    # Get recent comments
    print("Fetching recent comments...")
    comments = get_recent_comments(youtube, channel_id)
    print(f"  Found {len(comments)} recent comments")

    # Load already responded
    responded_data = load_responded_comments()
    responded_ids = set(responded_data["responded"])

    replies_posted = 0
    video_title_cache = {}

    for comment in comments:
        if replies_posted >= max_replies:
            print(f"  Reached max replies ({max_replies})")
            break

        # Skip if already responded
        if comment["comment_id"] in responded_ids:
            continue

        # Skip comments posted by the channel itself (e.g. engagement booster comments)
        if comment.get("author_channel_id") == channel_id:
            responded_ids.add(comment["comment_id"])
            continue

        # Skip if channel already replied
        if comment["reply_count"] > 0:
            if has_channel_reply(youtube, comment["thread_id"], channel_id):
                responded_ids.add(comment["comment_id"])
                continue

        # Get video title (cached)
        video_id = comment["video_id"]
        if video_id not in video_title_cache:
            video_title_cache[video_id] = get_video_title(youtube, video_id)
        video_title = video_title_cache[video_id]

        # Generate reply
        print(f"\n  Comment by {comment['author']}: \"{comment['text'][:80]}...\"")
        reply = generate_reply(comment["text"], video_title)

        if not reply:
            print("    Failed to generate reply, skipping")
            continue

        print(f"    Reply: \"{reply[:80]}...\"")

        if not dry_run:
            try:
                post_reply(youtube, comment["thread_id"], reply)
                print("    Posted!")
                replies_posted += 1
                responded_ids.add(comment["comment_id"])
            except Exception as e:
                print(f"    Error posting: {e}")
        else:
            print("    (dry run - not posting)")
            replies_posted += 1

    # Save responded list
    responded_data["responded"] = list(responded_ids)[-500:]  # Keep last 500
    save_responded_comments(responded_data)

    print(f"\nReplied to {replies_posted} comments")
    return replies_posted


def main():
    parser = argparse.ArgumentParser(description="YouTube Comment Responder Bot")
    parser.add_argument("--max-replies", type=int, default=5,
                        help="Max replies to post per run (default: 5)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Generate replies without posting")
    args = parser.parse_args()

    youtube = get_authenticated_service()
    process_comments(youtube, max_replies=args.max_replies, dry_run=args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
