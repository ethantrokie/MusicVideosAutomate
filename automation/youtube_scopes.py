"""
Shared YouTube OAuth scopes.
All scripts that use YouTube APIs should import from here.
"""

SCOPES = [
    'https://www.googleapis.com/auth/youtube.force-ssl',      # Upload and manage videos
    'https://www.googleapis.com/auth/yt-analytics.readonly',  # Read analytics data
]
