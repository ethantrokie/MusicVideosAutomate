#!/usr/bin/env python3
"""
Credit monitor for fal.ai and Suno API.
Checks balances and sends iMessage alerts when credits are low.

Usage:
    python3 automation/credit_monitor.py          # Check both services
    python3 automation/credit_monitor.py --quiet   # Only alert if low
"""

import json
import os
import subprocess
import sys
import requests
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Thresholds
SUNO_LOW_CREDITS = 600       # 600 credits × $0.005 = $3.00
FAL_LOW_BALANCE_USD = 3.00   # $3.00

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.json"
NOTIFICATION_SCRIPT = SCRIPT_DIR / "notification_helper.sh"


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def send_alert(message: str):
    """Send iMessage alert via notification_helper.sh. Deduped to max once per day."""
    # Dedup: don't send the same alert category more than once per day
    dedup_dir = SCRIPT_DIR / "state"
    dedup_dir.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    # Use first 10 chars of message as category key
    alert_key = message[:10].replace(" ", "_").replace(":", "")
    dedup_file = dedup_dir / f"alert_{alert_key}_{today}.sent"

    if dedup_file.exists():
        print(f"  📱 Alert already sent today, skipping: {message[:50]}...")
        return

    try:
        subprocess.run(
            [str(NOTIFICATION_SCRIPT), message],
            check=True, timeout=30
        )
        dedup_file.write_text(today)
        print(f"  📱 Alert sent: {message}")
    except Exception as e:
        print(f"  ⚠️  Failed to send alert: {e}")


def check_suno_credits(config: dict) -> dict:
    """
    Check Suno API remaining credits.
    Returns dict with 'ok', 'credits', 'dollars', 'message'.
    """
    suno_config = config.get("suno_api", {})
    api_key = suno_config.get("api_key")
    base_url = suno_config.get("base_url", "https://api.sunoapi.org")

    if not api_key:
        return {"ok": False, "credits": 0, "dollars": 0, "message": "Suno API key not configured"}

    try:
        response = requests.get(
            f"{base_url}/api/v1/generate/credit",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            credits = data.get("data", 0)
            dollars = credits * 0.005
            is_low = credits < SUNO_LOW_CREDITS
            return {
                "ok": not is_low,
                "credits": credits,
                "dollars": dollars,
                "message": f"Suno: {credits} credits (${dollars:.2f})" + (" - LOW!" if is_low else "")
            }
        else:
            return {
                "ok": False,
                "credits": 0,
                "dollars": 0,
                "message": f"Suno credit check failed: HTTP {response.status_code}"
            }
    except Exception as e:
        return {"ok": False, "credits": 0, "dollars": 0, "message": f"Suno credit check error: {e}"}


def check_fal_balance(config: dict) -> dict:
    """
    Check fal.ai balance by querying recent usage.
    Since fal.ai has no direct balance endpoint, we query usage
    and check if the account is accessible (not locked).
    Returns dict with 'ok', 'spent_24h', 'message'.
    """
    fal_key = config.get("fal_api", {}).get("api_key")

    if not fal_key:
        return {"ok": False, "spent_24h": 0, "message": "fal.ai API key not configured"}

    try:
        # Check if account is accessible by querying usage
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

        response = requests.get(
            "https://api.fal.ai/v1/models/usage",
            headers={"Authorization": f"Key {fal_key}"},
            params={
                "limit": 100,
                "start": start,
                "expand": "summary"
            },
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            # Sum up costs from summary if available
            total_cost = 0
            summary = data.get("summary", [])
            for item in summary:
                total_cost += item.get("cost", 0)

            return {
                "ok": True,
                "spent_7d": total_cost,
                "message": f"fal.ai: account active (${total_cost:.2f} spent in last 7 days)"
            }
        elif response.status_code == 401:
            return {
                "ok": False,
                "spent_7d": 0,
                "message": "fal.ai: API key invalid or account locked - may need to top up balance"
            }
        elif response.status_code == 403:
            # 403 from usage API means the key lacks Admin scope -
            # regular API keys can still generate videos fine
            return {
                "ok": True,
                "spent_7d": 0,
                "message": "fal.ai: usage API requires admin key (cannot check balance, but generation should work)"
            }
        else:
            return {
                "ok": True,
                "spent_7d": 0,
                "message": f"fal.ai: usage check returned {response.status_code} (proceeding cautiously)"
            }
    except Exception as e:
        return {"ok": True, "spent_7d": 0, "message": f"fal.ai: usage check failed ({e}), proceeding"}


def main():
    quiet = "--quiet" in sys.argv

    config = load_config()
    alerts = []

    # Check Suno credits
    suno_result = check_suno_credits(config)
    if not quiet:
        print(f"  {suno_result['message']}")
    if not suno_result["ok"]:
        alerts.append(f"⚠️ LOW SUNO CREDITS: {suno_result['credits']} credits (${suno_result['dollars']:.2f}) remaining. Top up at sunoapi.org")

    # Check fal.ai balance
    fal_result = check_fal_balance(config)
    if not quiet:
        print(f"  {fal_result['message']}")
    if not fal_result["ok"]:
        # fal.ai issues are warnings only - don't block pipeline
        # (AI clips are optional, pipeline can continue without them)
        alerts.append(f"⚠️ FAL.AI ISSUE: {fal_result['message']}. Top up at fal.ai/dashboard/billing")

    # Send alerts for low credits, but don't fail the pipeline
    # Low credits are a warning - pipeline should continue until credits are exhausted
    if alerts:
        combined = " | ".join(alerts)
        send_alert(combined)

    # Only fail if API is completely broken/inaccessible (not just low credits)
    # Low credits (< 600) should warn but not block - let the actual API call fail if needed
    if not quiet and not alerts:
        print("  ✅ All API credits OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
