#!/usr/bin/env python3
"""
TikTok Video Uploader with OAuth 2.0 Authentication

Uploads videos to TikTok using the Content Posting API with OAuth 2.0 authentication.
Handles chunked video upload, status polling, and token management.

Usage:
    ./automation/tiktok_uploader.py --auth                    # Authenticate (first time)
    ./automation/tiktok_uploader.py --video path/to/video.mp4 --title "My Video" --caption "Caption text"
"""

import argparse
import base64
import hashlib
import json
import os
import pickle
import secrets
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import requests

# TikTok API Configuration
TIKTOK_API_BASE = "https://open.tiktokapis.com"
TIKTOK_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = f"{TIKTOK_API_BASE}/v2/oauth/token/"

# File paths
SCRIPT_DIR = Path(__file__).parent.parent
CREDENTIALS_PATH = SCRIPT_DIR / "config" / "tiktok_credentials.json"
TOKEN_CACHE_PATH = SCRIPT_DIR / "config" / "tiktok_token.pickle"

# OAuth callback server
CALLBACK_PORT = 8080
authorization_code = None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback"""

    def do_GET(self):
        """Handle GET request with authorization code"""
        global authorization_code

        # Parse query parameters
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        if 'code' in params:
            authorization_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h1>Authorization successful!</h1><p>You can close this window.</p></body></html>')
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h1>Authorization failed</h1><p>No authorization code received.</p></body></html>')

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


class TikTokUploader:
    """TikTok video uploader with OAuth 2.0 authentication"""

    def __init__(self):
        self.credentials = self._load_credentials()
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = None
        self.code_verifier = None
        self.code_challenge = None

        # Try to load saved tokens
        self._load_tokens()

    def _load_credentials(self):
        """Load OAuth credentials from JSON file"""
        if not CREDENTIALS_PATH.exists():
            raise FileNotFoundError(
                f"Credentials file not found: {CREDENTIALS_PATH}\n"
                f"Please copy config/tiktok_credentials.json.template to config/tiktok_credentials.json "
                f"and fill in your Client Key and Client Secret from developers.tiktok.com"
            )

        with open(CREDENTIALS_PATH, 'r') as f:
            return json.load(f)

    def _save_tokens(self):
        """Save tokens to pickle file"""
        token_data = {
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'token_expiry': self.token_expiry
        }
        with open(TOKEN_CACHE_PATH, 'wb') as f:
            pickle.dump(token_data, f)
        print(f"✅ Tokens saved to {TOKEN_CACHE_PATH}")

    def _load_tokens(self):
        """Load tokens from pickle file"""
        if not TOKEN_CACHE_PATH.exists():
            return False

        try:
            with open(TOKEN_CACHE_PATH, 'rb') as f:
                token_data = pickle.load(f)

            self.access_token = token_data['access_token']
            self.refresh_token = token_data['refresh_token']
            self.token_expiry = token_data['token_expiry']
            return True
        except Exception as e:
            print(f"⚠️  Failed to load tokens: {e}")
            return False

    def _is_token_expired(self):
        """Check if access token is expired"""
        if not self.token_expiry:
            return True
        return time.time() >= self.token_expiry

    def _generate_pkce_params(self):
        """Generate PKCE parameters for TikTok OAuth 2.0

        NOTE: TikTok uses NON-STANDARD PKCE implementation!
        They require hex encoding instead of base64url encoding for code_challenge.
        Standard: code_challenge = base64url(SHA256(code_verifier))
        TikTok:   code_challenge = hex(SHA256(code_verifier))
        """
        # Generate random code verifier (43-128 characters)
        self.code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

        # Generate code challenge - TikTok requires HEX encoding (not base64url!)
        self.code_challenge = hashlib.sha256(self.code_verifier.encode('utf-8')).hexdigest()

    def _refresh_access_token(self):
        """Refresh expired access token"""
        print("🔄 Refreshing access token...")

        data = {
            'client_key': self.credentials['client_key'],
            'client_secret': self.credentials['client_secret'],
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token
        }

        response = requests.post(TIKTOK_TOKEN_URL, data=data)
        response.raise_for_status()

        token_data = response.json()

        # Check for errors in response
        if 'error' in token_data:
            raise Exception(f"TikTok API error during refresh: {token_data.get('error')} - {token_data.get('error_description', 'No description')}")

        if 'access_token' not in token_data:
            raise Exception(f"No access_token in refresh response. Full response: {token_data}")

        self.access_token = token_data['access_token']
        self.refresh_token = token_data.get('refresh_token', self.refresh_token)
        self.token_expiry = time.time() + token_data['expires_in']

        self._save_tokens()
        print("✅ Access token refreshed")

    def authenticate(self):
        """Perform OAuth 2.0 authentication flow"""
        global authorization_code

        # Try loading cached tokens
        if self._load_tokens():
            if not self._is_token_expired():
                print("✅ Using cached access token")
                return
            else:
                print("⚠️  Cached token expired, refreshing...")
                try:
                    self._refresh_access_token()
                    return
                except Exception as e:
                    print(f"⚠️  Token refresh failed: {e}")
                    print("Starting new authorization flow...")

        # Start OAuth flow
        print("🔐 Starting OAuth 2.0 authorization flow...")

        # Generate PKCE parameters
        self._generate_pkce_params()

        # Build authorization URL with PKCE
        params = {
            'client_key': self.credentials['client_key'],
            'scope': 'video.publish',
            'response_type': 'code',
            'redirect_uri': self.credentials['redirect_uri'],
            'code_challenge': self.code_challenge,
            'code_challenge_method': 'S256'
        }
        auth_url = f"{TIKTOK_AUTH_URL}?{urllib.parse.urlencode(params)}"

        print(f"Opening browser for authorization: {auth_url}")
        print(f"Redirect URI: {self.credentials['redirect_uri']}")
        print("ℹ️  If you see a 'redirect_uri' error, ensure this URI exactly matches your TikTok App settings.")
        webbrowser.open(auth_url)

        # Start local callback server
        print(f"Starting callback server on port {CALLBACK_PORT}...")
        server = HTTPServer(('localhost', CALLBACK_PORT), OAuthCallbackHandler)

        # Wait for callback (with timeout)
        timeout = 300  # 5 minutes
        start_time = time.time()
        while authorization_code is None:
            server.handle_request()
            if time.time() - start_time > timeout:
                raise TimeoutError("Authorization timeout - no code received")

        print("✅ Authorization code received")

        # Exchange authorization code for access token
        print("Exchanging authorization code for access token...")
        data = {
            'client_key': self.credentials['client_key'],
            'client_secret': self.credentials['client_secret'],
            'code': authorization_code,
            'grant_type': 'authorization_code',
            'redirect_uri': self.credentials['redirect_uri'],
            'code_verifier': self.code_verifier
        }

        response = requests.post(TIKTOK_TOKEN_URL, data=data)
        response.raise_for_status()

        token_data = response.json()

        # Check for errors in response
        if 'error' in token_data:
            raise Exception(f"TikTok API error: {token_data.get('error')} - {token_data.get('error_description', 'No description')}")

        if 'access_token' not in token_data:
            raise Exception(f"No access_token in response. Full response: {token_data}")

        self.access_token = token_data['access_token']
        self.refresh_token = token_data['refresh_token']
        self.token_expiry = time.time() + token_data['expires_in']

        self._save_tokens()
        print("✅ Authentication successful!")

    def upload_video(self, video_path, title, caption, privacy_level="public_to_everyone"):
        """
        Upload video to TikTok

        Args:
            video_path: Path to video file
            title: Video title
            caption: Video caption (description)
            privacy_level: Privacy setting (public_to_everyone, mutual_follow_friends, self_only)

        Returns:
            dict: Upload result with video ID and URL
        """
        # Ensure authentication
        if not self.access_token or self._is_token_expired():
            self._refresh_access_token()

        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        video_size = video_path.stat().st_size
        print(f"📤 Uploading video: {video_path.name} ({video_size / (1024*1024):.2f} MB)")

        # Step 1: Initialize upload
        print("Initializing upload...")
        init_data = {
            "post_info": {
                "title": title,
                "privacy_level": privacy_level,
                "disable_comment": False,
                "disable_duet": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": min(video_size, 10 * 1024 * 1024),  # 10 MB chunks
                "total_chunk_count": (video_size + 10 * 1024 * 1024 - 1) // (10 * 1024 * 1024)
            }
        }

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        }

        response = requests.post(
            f"{TIKTOK_API_BASE}/v2/post/publish/video/init/",
            headers=headers,
            json=init_data
        )

        # Check for specific errors
        if response.status_code == 403:
            try:
                error_data = response.json()
                error_code = error_data.get('error', {}).get('code', '')

                if error_code == 'unaudited_client_can_only_post_to_private_accounts':
                    raise Exception(
                        "\n❌ SANDBOX MODE ERROR: Your TikTok app can only post to private accounts.\n"
                        "\n"
                        "Required steps to fix:\n"
                        "1. Open TikTok mobile app → Settings → Privacy\n"
                        "2. Set your account to 'Private Account' (toggle ON)\n"
                        "3. Go to developers.tiktok.com → Your App → 'Test Users'\n"
                        "4. Add your TikTok account as a test user\n"
                        "5. Re-run authentication: ./automation/tiktok_uploader.py --auth\n"
                        "6. Try upload again with --privacy=self_only\n"
                        "\n"
                        "Note: In sandbox mode, videos can only be posted with SELF_ONLY privacy.\n"
                        "To post publicly, you must submit your app for TikTok's review.\n"
                    )
            except Exception as e:
                # Re-raise our custom exception
                if "SANDBOX MODE ERROR" in str(e):
                    raise
                # Otherwise continue to generic error

        response.raise_for_status()

        init_result = response.json()
        publish_id = init_result['data']['publish_id']
        upload_url = init_result['data']['upload_url']

        print(f"✅ Upload initialized (publish_id: {publish_id})")

        # Step 2: Upload video chunks
        print("Uploading video chunks...")
        chunk_size = 10 * 1024 * 1024  # 10 MB

        with open(video_path, 'rb') as f:
            chunk_num = 0
            while True:
                chunk_data = f.read(chunk_size)
                if not chunk_data:
                    break

                chunk_num += 1
                print(f"  Uploading chunk {chunk_num}...")

                upload_response = requests.put(
                    upload_url,
                    headers={"Content-Type": "video/mp4"},
                    data=chunk_data
                )
                upload_response.raise_for_status()

        print(f"✅ All {chunk_num} chunks uploaded")

        # Step 3: Poll for status
        print("Waiting for video processing...")
        max_attempts = 60
        for attempt in range(max_attempts):
            time.sleep(5)  # Wait 5 seconds between checks

            status_response = requests.post(
                f"{TIKTOK_API_BASE}/v2/post/publish/status/fetch/",
                headers=headers,
                json={"publish_id": publish_id}
            )
            status_response.raise_for_status()

            status_data = status_response.json()
            status = status_data['data']['status']

            if status == "PUBLISH_COMPLETE":
                video_id = status_data['data']['publicize_status_info']['video_id']
                print(f"✅ Video published successfully!")
                print(f"   Video ID: {video_id}")

                # Construct video URL
                # Note: Replace with actual TikTok username
                video_url = f"https://www.tiktok.com/@YOUR_USERNAME/video/{video_id}"
                print(f"   Video URL: {video_url}")

                return {
                    "id": video_id,
                    "url": video_url,
                    "status": "success"
                }
            elif status == "FAILED":
                error_msg = status_data['data'].get('fail_reason', 'Unknown error')
                raise Exception(f"Video upload failed: {error_msg}")
            else:
                print(f"  Status: {status} (attempt {attempt + 1}/{max_attempts})")

        raise TimeoutError("Video processing timeout - status check exceeded maximum attempts")


def main():
    parser = argparse.ArgumentParser(description="Upload videos to TikTok")
    parser.add_argument("--auth", action="store_true", help="Authenticate with TikTok")
    parser.add_argument("--video", help="Path to video file")
    parser.add_argument("--title", help="Video title")
    parser.add_argument("--caption", help="Video caption")
    parser.add_argument("--privacy", default="public_to_everyone",
                       choices=["public_to_everyone", "mutual_follow_friends", "self_only"],
                       help="Privacy level")

    args = parser.parse_args()

    uploader = TikTokUploader()

    if args.auth:
        # Authentication only
        uploader.authenticate()
    elif args.video:
        # Upload video
        if not args.title:
            parser.error("--title is required when uploading a video")

        caption = args.caption or args.title

        result = uploader.upload_video(
            video_path=args.video,
            title=args.title,
            caption=caption,
            privacy_level=args.privacy
        )

        # Print result as JSON for parsing by shell scripts
        print(json.dumps(result))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
