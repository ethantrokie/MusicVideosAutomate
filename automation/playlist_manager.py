#!/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/venv/bin/python3
"""
Playlist Manager - Auto-organizes videos into category-based playlists.
Uses YouTube Data API v3 to create playlists and assign videos.
"""

import json
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from youtube_channel_helper import get_authenticated_service


# Category-to-playlist mapping with keywords for auto-detection
CATEGORY_PLAYLISTS = {
    "Engineering & Manufacturing": {
        "description": "Science songs about how things are made and engineered",
        "keywords": [
            "laser", "cnc", "injection", "molding", "forging", "welding", "casting",
            "machining", "assembly", "factory", "manufacturing", "production", "steel",
            "aluminum", "extrud", "stamping", "3d print", "fabricat", "engine",
            "turbine", "gear", "transmission", "hydraulic", "pneumatic", "piston",
            "generator", "transformer", "bridge", "dam", "conveyor", "elevator",
            "crane", "pump", "valve", "bearing", "spring", "bolt", "rivet"
        ]
    },
    "Physics & Energy": {
        "description": "Science songs about physics, waves, energy, and forces",
        "keywords": [
            "light", "wave", "energy", "force", "motion", "momentum", "doppler",
            "polariz", "refraction", "reflection", "magnetic", "electric", "quantum",
            "gravity", "friction", "pressure", "temperature", "heat", "sound",
            "optic", "laser", "spectrum", "radiation", "nuclear", "particle"
        ]
    },
    "Chemistry & Materials": {
        "description": "Science songs about chemical reactions and materials science",
        "keywords": [
            "molecule", "chemical", "reaction", "atom", "element", "compound",
            "catalyst", "oxidation", "reduction", "bond", "polymer", "crystal",
            "alloy", "ceramic", "composite", "glass", "plastic", "rubber",
            "corrosion", "electroplat", "anodiz", "temper", "vapor deposition"
        ]
    },
    "Biology & Nature": {
        "description": "Science songs about life, cells, and natural processes",
        "keywords": [
            "cell", "dna", "protein", "photosynthesis", "bacteria", "evolution",
            "gene", "organism", "ecosystem", "brain", "neuron", "muscle",
            "kidney", "eye", "blood", "immune", "virus", "plant", "animal",
            "bioluminesc", "metamorpho", "enzyme", "hormone"
        ]
    },
    "Computer Science & Tech": {
        "description": "Science songs about algorithms, data, and technology",
        "keywords": [
            "algorithm", "data structure", "hash", "binary", "encryption",
            "network", "internet", "processor", "semiconductor", "circuit",
            "database", "sql", "code", "software", "fiber optic", "wifi",
            "bluetooth", "gps", "satellite", "robot", "artificial intelligence"
        ]
    },
    "Earth & Space": {
        "description": "Science songs about our planet and the universe",
        "keywords": [
            "ocean", "hurricane", "rock", "tectonic", "volcano", "earthquake",
            "weather", "climate", "glacier", "erosion", "fossil", "mineral",
            "atmosphere", "ozone", "star", "planet", "galaxy", "solar",
            "moon", "asteroid", "comet", "nebula"
        ]
    }
}


def detect_category(title):
    """Detect the best category for a video based on its title."""
    title_lower = title.lower()
    scores = {}

    for category, config in CATEGORY_PLAYLISTS.items():
        score = sum(1 for kw in config["keywords"] if kw in title_lower)
        if score > 0:
            scores[category] = score

    if scores:
        return max(scores, key=scores.get)
    return "Engineering & Manufacturing"  # Default to strongest category


def get_or_create_playlist(youtube, title, description):
    """Get existing playlist by title or create new one."""
    # Search existing playlists
    request = youtube.playlists().list(
        part="snippet",
        mine=True,
        maxResults=50
    )
    response = request.execute()

    for item in response.get("items", []):
        if item["snippet"]["title"] == title:
            return item["id"]

    # Create new playlist
    request = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": description
            },
            "status": {
                "privacyStatus": "public"
            }
        }
    )
    response = request.execute()
    print(f"  Created playlist: {title}")
    return response["id"]


def add_video_to_playlist(youtube, playlist_id, video_id):
    """Add a video to a playlist."""
    request = youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id
                }
            }
        }
    )
    response = request.execute()
    return response


def organize_video(youtube, video_id, title):
    """Auto-detect category and add video to the right playlist."""
    category = detect_category(title)
    config = CATEGORY_PLAYLISTS[category]

    playlist_id = get_or_create_playlist(
        youtube,
        f"Learning Science Music: {category}",
        config["description"]
    )

    try:
        add_video_to_playlist(youtube, playlist_id, video_id)
        print(f"  Added '{title[:50]}...' to '{category}'")
        return category
    except Exception as e:
        if "duplicate" in str(e).lower() or "already" in str(e).lower():
            print(f"  Already in playlist: {category}")
            return category
        raise


def organize_recent_videos(youtube, days=7):
    """Organize all recent videos into playlists."""
    from datetime import datetime, timedelta

    since = (datetime.now() - timedelta(days=days)).isoformat() + 'Z'

    # Get channel ID
    channels = youtube.channels().list(part='id', mine=True).execute()
    channel_id = channels['items'][0]['id']

    # Get recent videos
    request = youtube.search().list(
        part='id,snippet',
        channelId=channel_id,
        maxResults=50,
        order='date',
        publishedAfter=since,
        type='video'
    )
    response = request.execute()

    organized = 0
    for item in response.get('items', []):
        video_id = item['id']['videoId']
        title = item['snippet']['title']
        try:
            organize_video(youtube, video_id, title)
            organized += 1
        except Exception as e:
            print(f"  Error organizing {video_id}: {e}")

    print(f"\nOrganized {organized} videos into playlists")


def main():
    parser = argparse.ArgumentParser(description="YouTube Playlist Manager")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="Add a video to its category playlist")
    add_parser.add_argument("--video-id", required=True)
    add_parser.add_argument("--title", required=True)

    organize_parser = subparsers.add_parser("organize", help="Organize recent videos")
    organize_parser.add_argument("--days", type=int, default=7)

    subparsers.add_parser("create-all", help="Create all category playlists")

    args = parser.parse_args()

    youtube = get_authenticated_service()

    if args.command == "add":
        organize_video(youtube, args.video_id, args.title)
    elif args.command == "organize":
        organize_recent_videos(youtube, args.days)
    elif args.command == "create-all":
        for category, config in CATEGORY_PLAYLISTS.items():
            playlist_title = f"Learning Science Music: {category}"
            get_or_create_playlist(youtube, playlist_title, config["description"])
            print(f"  Ensured playlist: {playlist_title}")
    else:
        parser.print_help()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
