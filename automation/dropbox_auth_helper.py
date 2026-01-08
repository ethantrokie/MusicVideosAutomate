#!/usr/bin/env python3
"""
Helper script to authenticate with Dropbox and get a refresh token.
This refresh token can be used to automatically generate new access tokens.

Usage:
    python automation/dropbox_auth_helper.py
"""

import json
import webbrowser
from pathlib import Path
from dropbox import DropboxOAuth2FlowNoRedirect

CONFIG_PATH = Path("config/config.json")


def load_config():
    """Load current config."""
    with open(CONFIG_PATH) as f:
        return json.load(f)


def save_config(config):
    """Save updated config."""
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)


def get_refresh_token():
    """
    Perform OAuth flow to get a refresh token.
    This only needs to be done once - the refresh token doesn't expire.
    """
    config = load_config()

    app_key = config['dropbox']['app_key']
    app_secret = config['dropbox']['app_secret']

    print("=" * 60)
    print("Dropbox Refresh Token Setup")
    print("=" * 60)
    print()
    print("This will get a refresh token that auto-renews access tokens.")
    print("You only need to do this once!")
    print()

    # Initialize OAuth flow
    auth_flow = DropboxOAuth2FlowNoRedirect(
        app_key,
        app_secret,
        token_access_type='offline'  # Request refresh token
    )

    # Get authorization URL
    authorize_url = auth_flow.start()

    print("1. Opening browser to Dropbox authorization page...")
    print(f"   URL: {authorize_url}")
    print()

    # Try to open browser automatically
    try:
        webbrowser.open(authorize_url)
        print("   ✓ Browser opened automatically")
    except:
        print("   ⚠️ Couldn't open browser automatically")
        print("   Please open the URL above manually")

    print()
    print("2. Click 'Allow' to authorize the app")
    print("3. Copy the authorization code from the browser")
    print()

    # Get authorization code from user
    auth_code = input("Enter the authorization code here: ").strip()

    try:
        # Exchange code for refresh token
        oauth_result = auth_flow.finish(auth_code)

        refresh_token = oauth_result.refresh_token
        access_token = oauth_result.access_token

        print()
        print("=" * 60)
        print("✅ SUCCESS! Refresh token obtained")
        print("=" * 60)
        print()
        print("Updating config.json with refresh token...")

        # Update config
        config['dropbox']['refresh_token'] = refresh_token
        config['dropbox']['access_token'] = access_token

        save_config(config)

        print("✅ Config updated!")
        print()
        print("Your Dropbox authentication is now set up.")
        print("Access tokens will auto-refresh automatically.")
        print()

    except Exception as e:
        print()
        print(f"❌ Error: {e}")
        print()
        print("Please try again. Make sure you:")
        print("  1. Clicked 'Allow' on the Dropbox page")
        print("  2. Copied the entire authorization code")
        print()
        return False

    return True


if __name__ == "__main__":
    success = get_refresh_token()
    exit(0 if success else 1)
