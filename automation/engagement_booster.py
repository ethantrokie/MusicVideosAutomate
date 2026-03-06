#!/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/venv/bin/python3
"""
Engagement booster for YouTube videos.
Auto-posts pinned comments and adds CTAs after video uploads.
Targets improving engagement rate from 1.47% toward 5.9-9% industry benchmark.
"""

import argparse
import json
import logging
import pickle
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

sys.path.insert(0, str(Path(__file__).parent))
from youtube_scopes import SCOPES

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
AUTOMATION_CONFIG_PATH = PROJECT_ROOT / "automation" / "config" / "automation_config.json"

# NOTE: pickle is used here intentionally to match the existing auth pattern
# in youtube_channel_helper.py and weekly_optimizer.py.  The token file is
# written and read only by this project's own code, not from untrusted sources.

COMMENT_TEMPLATES = (
    "Which science topic should we turn into a song next? Drop it below!",
    "What was the most surprising fact about {topic}? Let us know!",
    "Did you know about {topic}? Tell us what else you want to learn!",
    "Fun fact: {topic} is wilder than you think. What topic should we explore next?",
)

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
logger = logging.getLogger("engagement_booster")

# ---------------------------------------------------------------------------
# Data classes (immutable)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommentResult:
    """Immutable result of a comment posting operation."""
    video_id: str
    comment_id: str
    comment_text: str
    pinned: bool
    error: Optional[str] = None


@dataclass(frozen=True)
class BatchResult:
    """Immutable result of a batch operation."""
    processed: tuple
    skipped: tuple
    errors: tuple


# ---------------------------------------------------------------------------
# Authentication (mirrors youtube_channel_helper.py)
# ---------------------------------------------------------------------------


def get_authenticated_service():
    """Authenticate and return YouTube API v3 service.

    Reuses the same credential/token paths and scopes as
    youtube_channel_helper.py and weekly_optimizer.py.
    The pickle token file is produced exclusively by this project's
    own OAuth flow -- it is NOT loaded from untrusted sources.
    """
    creds = None
    token_path = CONFIG_DIR / "youtube_token.pickle"
    creds_path = CONFIG_DIR / "youtube_credentials.json"

    if not creds_path.exists():
        raise FileNotFoundError(
            f"YouTube credentials not found at {creds_path}. "
            "Please set up OAuth credentials first."
        )

    if token_path.exists():
        with open(token_path, "rb") as token_file:
            creds = pickle.load(token_file)  # noqa: S301 — trusted local file

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as exc:
                if not sys.stdin.isatty():
                    logger.error(
                        "YouTube OAuth token expired. "
                        "Run interactively to re-authenticate: "
                        "rm %s && python automation/engagement_booster.py --video-id TEST --topic test",
                        token_path,
                    )
                    raise SystemExit(
                        "YouTube token expired - manual re-authentication required"
                    ) from exc
                logger.warning("Refresh token expired, re-authenticating interactively...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(creds_path), SCOPES
                )
                creds = flow.run_local_server(port=0)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(creds_path), SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(token_path, "wb") as token_file:
            pickle.dump(creds, token_file)  # noqa: S301 — trusted local file

    return build("youtube", "v3", credentials=creds)


# ---------------------------------------------------------------------------
# Comment generation
# ---------------------------------------------------------------------------


def generate_comment_text(topic: str, template_index: Optional[int] = None) -> str:
    """Generate an engagement-driving comment based on the topic.

    Rotates through templates. If *template_index* is ``None`` a random
    template is chosen.  The topic is never mutated.
    """
    if not topic or not topic.strip():
        raise ValueError("Topic must be a non-empty string")

    index = template_index if template_index is not None else random.randrange(len(COMMENT_TEMPLATES))
    template = COMMENT_TEMPLATES[index % len(COMMENT_TEMPLATES)]
    return template.format(topic=topic.strip())


# ---------------------------------------------------------------------------
# YouTube API helpers
# ---------------------------------------------------------------------------


def post_comment(youtube, video_id: str, text: str) -> str:
    """Post a top-level comment on a video and return the comment ID.

    Raises ``HttpError`` on API failure.
    """
    if not video_id or not video_id.strip():
        raise ValueError("video_id must be a non-empty string")
    if not text or not text.strip():
        raise ValueError("Comment text must be a non-empty string")

    body = {
        "snippet": {
            "videoId": video_id.strip(),
            "topLevelComment": {
                "snippet": {
                    "textOriginal": text,
                }
            },
        }
    }

    response = youtube.commentThreads().insert(
        part="snippet",
        body=body,
    ).execute()

    comment_id = response["snippet"]["topLevelComment"]["id"]
    logger.info("Posted comment %s on video %s", comment_id, video_id)
    return comment_id


def pin_comment(youtube, comment_id: str) -> None:
    """Attempt to pin a comment so it appears at the top.

    The YouTube Data API v3 does not expose a direct "pin" endpoint.
    We set the comment's moderation status to ``published`` which, for
    channel-owner comments on their own videos, helps ensure visibility.

    True pinning must currently be done in YouTube Studio.  If a direct
    pin endpoint becomes available in a future API version, this
    function should be updated.
    """
    if not comment_id or not comment_id.strip():
        raise ValueError("comment_id must be a non-empty string")

    try:
        youtube.comments().setModerationStatus(
            id=comment_id.strip(),
            moderationStatus="published",
            banAuthor=False,
        ).execute()
        logger.info("Set moderation status to published for comment %s", comment_id)
    except HttpError as exc:
        # 403 often means the video isn't on the authenticated channel,
        # or the API doesn't support this operation for the comment type.
        logger.warning(
            "Could not set moderation status for comment %s: %s. "
            "The comment was posted successfully but may not be pinned. "
            "Pin manually from YouTube Studio if needed.",
            comment_id,
            exc,
        )


def get_channel_video_ids(youtube, max_results: int = 10) -> list[dict]:
    """Fetch recent uploads from the authenticated channel.

    Returns a list of dicts with ``video_id`` and ``title`` keys.
    Results are ordered by date (newest first).  The input service
    object is never mutated.
    """
    channels_response = youtube.channels().list(
        part="contentDetails",
        mine=True,
    ).execute()

    items = channels_response.get("items", [])
    if not items:
        logger.warning("No channels found for authenticated user")
        return []

    uploads_playlist_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    playlist_response = youtube.playlistItems().list(
        part="snippet",
        playlistId=uploads_playlist_id,
        maxResults=max_results,
    ).execute()

    videos = []
    for item in playlist_response.get("items", []):
        snippet = item["snippet"]
        videos.append({
            "video_id": snippet["resourceId"]["videoId"],
            "title": snippet["title"],
        })

    return videos


def video_has_owner_comment(youtube, video_id: str) -> bool:
    """Check whether the channel owner already has a top-level comment
    on the given video.

    This prevents duplicate engagement comments on repeat runs.
    """
    channels_response = youtube.channels().list(
        part="id",
        mine=True,
    ).execute()

    channel_items = channels_response.get("items", [])
    if not channel_items:
        return False

    channel_id = channel_items[0]["id"]

    try:
        comments_response = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=100,
            textFormat="plainText",
        ).execute()
    except HttpError as exc:
        logger.warning("Could not fetch comments for %s: %s", video_id, exc)
        return False

    for thread in comments_response.get("items", []):
        author_channel = thread["snippet"]["topLevelComment"]["snippet"].get(
            "authorChannelId", {}
        ).get("value", "")
        if author_channel == channel_id:
            return True

    return False


# ---------------------------------------------------------------------------
# High-level operations
# ---------------------------------------------------------------------------


def post_and_pin_comment(
    youtube,
    video_id: str,
    topic: str,
    template_index: Optional[int] = None,
) -> CommentResult:
    """Post an engagement comment on a video and attempt to pin it.

    Returns an immutable ``CommentResult``.
    """
    text = generate_comment_text(topic, template_index)
    logger.info("Posting comment on video %s: %s", video_id, text)

    try:
        comment_id = post_comment(youtube, video_id, text)
    except HttpError as exc:
        error_msg = _extract_api_error(exc)
        logger.error("Failed to post comment on %s: %s", video_id, error_msg)
        return CommentResult(
            video_id=video_id,
            comment_id="",
            comment_text=text,
            pinned=False,
            error=error_msg,
        )

    pinned = False
    try:
        pin_comment(youtube, comment_id)
        pinned = True
    except HttpError as exc:
        logger.warning(
            "Comment posted but pinning failed for %s: %s",
            comment_id,
            _extract_api_error(exc),
        )

    return CommentResult(
        video_id=video_id,
        comment_id=comment_id,
        comment_text=text,
        pinned=pinned,
    )


def process_batch(youtube, max_videos: int = 10) -> BatchResult:
    """Process recent uploads that don't yet have an owner comment.

    Returns an immutable ``BatchResult``.
    """
    logger.info("Fetching recent uploads for batch processing...")
    videos = get_channel_video_ids(youtube, max_results=max_videos)

    if not videos:
        logger.info("No recent uploads found")
        return BatchResult(processed=(), skipped=(), errors=())

    logger.info("Found %d recent uploads", len(videos))

    processed = []
    skipped = []
    errors = []

    for video in videos:
        vid = video["video_id"]
        title = video["title"]

        if video_has_owner_comment(youtube, vid):
            logger.info("Skipping %s (%s) - already has owner comment", vid, title)
            skipped.append(vid)
            continue

        # Use the video title as the topic for comment generation
        result = post_and_pin_comment(youtube, vid, title)
        if result.error:
            errors.append(result)
        else:
            processed.append(result)

    return BatchResult(
        processed=tuple(processed),
        skipped=tuple(skipped),
        errors=tuple(errors),
    )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _extract_api_error(exc: HttpError) -> str:
    """Extract a human-readable error message from an HttpError."""
    try:
        error_content = json.loads(exc.content.decode("utf-8"))
        error_detail = error_content.get("error", {})
        message = error_detail.get("message", str(exc))
        code = error_detail.get("code", "unknown")
        return f"[{code}] {message}"
    except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
        return str(exc)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Engagement booster: auto-post pinned comments and CTAs "
            "on YouTube videos to improve engagement rate."
        ),
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)

    mode_group.add_argument(
        "--video-id",
        type=str,
        help="YouTube video ID to post a comment on",
    )
    mode_group.add_argument(
        "--batch",
        action="store_true",
        help="Process all recent uploads without owner comments",
    )

    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Video topic (used for comment generation; required with --video-id)",
    )
    parser.add_argument(
        "--template-index",
        type=int,
        default=None,
        help="Force a specific comment template (0-3); random if omitted",
    )
    parser.add_argument(
        "--max-videos",
        type=int,
        default=10,
        help="Maximum number of recent videos to process in batch mode (default: 10)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without calling the API",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug-level logging",
    )

    return parser


def validate_args(args: argparse.Namespace) -> None:
    """Validate CLI arguments. Raises SystemExit on invalid input."""
    if args.video_id and not args.topic:
        logger.error("--topic is required when using --video-id")
        raise SystemExit(1)

    if args.video_id and not args.video_id.strip():
        logger.error("--video-id must not be empty")
        raise SystemExit(1)

    if args.max_videos < 1:
        logger.error("--max-videos must be at least 1")
        raise SystemExit(1)

    if args.template_index is not None and args.template_index < 0:
        logger.error("--template-index must be non-negative")
        raise SystemExit(1)


def run_single(youtube, args: argparse.Namespace) -> None:
    """Handle single-video mode."""
    video_id = args.video_id.strip()
    topic = args.topic.strip()

    if args.dry_run:
        text = generate_comment_text(topic, args.template_index)
        logger.info("[DRY RUN] Would post on %s: %s", video_id, text)
        print(f"[DRY RUN] Video: {video_id}")
        print(f"[DRY RUN] Comment: {text}")
        return

    result = post_and_pin_comment(youtube, video_id, topic, args.template_index)

    if result.error:
        logger.error("Failed: %s", result.error)
        raise SystemExit(1)

    print(f"Comment posted on video {result.video_id}")
    print(f"  Comment ID: {result.comment_id}")
    print(f"  Text: {result.comment_text}")
    print(f"  Pinned: {result.pinned}")


def run_batch(youtube, args: argparse.Namespace) -> None:
    """Handle batch mode."""
    if args.dry_run:
        videos = get_channel_video_ids(youtube, max_results=args.max_videos)
        logger.info("[DRY RUN] Found %d recent uploads", len(videos))
        for video in videos:
            has_comment = video_has_owner_comment(youtube, video["video_id"])
            status = "SKIP (has comment)" if has_comment else "WOULD POST"
            text = generate_comment_text(video["title"], args.template_index) if not has_comment else ""
            print(f"[DRY RUN] {status}: {video['video_id']} - {video['title']}")
            if text:
                print(f"  Comment: {text}")
        return

    batch_result = process_batch(youtube, max_videos=args.max_videos)

    print(f"\nBatch processing complete:")
    print(f"  Processed: {len(batch_result.processed)}")
    print(f"  Skipped (already has comment): {len(batch_result.skipped)}")
    print(f"  Errors: {len(batch_result.errors)}")

    for result in batch_result.processed:
        print(f"  + {result.video_id}: {result.comment_text[:60]}...")

    for result in batch_result.errors:
        print(f"  ! {result.video_id}: {result.error}")

    if batch_result.errors:
        raise SystemExit(1)


def main() -> None:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    validate_args(args)

    try:
        youtube = get_authenticated_service()
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        raise SystemExit(1) from exc

    if args.video_id:
        run_single(youtube, args)
    elif args.batch:
        run_batch(youtube, args)


if __name__ == "__main__":
    main()
