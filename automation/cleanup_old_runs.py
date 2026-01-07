#!/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/venv/bin/python3
"""
Cleanup script to delete pipeline runs older than 2 weeks.
Runs weekly as part of the automation maintenance.
"""

import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path


def cleanup_old_runs(runs_dir="outputs/runs", days_to_keep=14, dry_run=False):
    """
    Delete pipeline run directories older than specified days.

    Args:
        runs_dir: Directory containing pipeline runs
        days_to_keep: Number of days to keep runs (default: 14)
        dry_run: If True, only show what would be deleted without actually deleting

    Returns:
        tuple: (deleted_count, freed_mb, errors)
    """
    runs_path = Path(runs_dir)

    # Safety check: ensure we're in the right directory
    if not runs_path.exists():
        print(f"Error: {runs_dir} does not exist")
        return 0, 0, ["Directory not found"]

    if not runs_path.is_dir():
        print(f"Error: {runs_dir} is not a directory")
        return 0, 0, ["Not a directory"]

    # Calculate cutoff date
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    print(f"Cutoff date: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Keeping runs from the last {days_to_keep} days\n")

    deleted_count = 0
    freed_bytes = 0
    errors = []

    # Get all run directories
    run_dirs = [d for d in runs_path.iterdir() if d.is_dir()]

    if not run_dirs:
        print("No run directories found")
        return 0, 0, []

    print(f"Found {len(run_dirs)} total run directories")
    print("=" * 80)

    for run_dir in sorted(run_dirs):
        try:
            # Parse directory name (format: YYYYMMDD_HHMMSS)
            dir_name = run_dir.name

            # Validate directory name format
            if not dir_name or len(dir_name) < 8:
                print(f"⚠️  Skipping '{dir_name}': Invalid directory name format")
                continue

            # Extract date from directory name (first 8 characters: YYYYMMDD)
            try:
                date_str = dir_name[:8]
                run_date = datetime.strptime(date_str, "%Y%m%d")
            except ValueError:
                print(f"⚠️  Skipping '{dir_name}': Cannot parse date from directory name")
                continue

            # Calculate directory size
            dir_size = sum(f.stat().st_size for f in run_dir.rglob('*') if f.is_file())
            dir_size_mb = dir_size / (1024 * 1024)

            # Check if old enough to delete
            if run_date < cutoff_date:
                days_old = (datetime.now() - run_date).days

                if dry_run:
                    print(f"🔍 Would delete: {dir_name} ({days_old} days old, {dir_size_mb:.1f} MB)")
                else:
                    print(f"🗑️  Deleting: {dir_name} ({days_old} days old, {dir_size_mb:.1f} MB)")
                    shutil.rmtree(run_dir)
                    deleted_count += 1
                    freed_bytes += dir_size
            else:
                days_old = (datetime.now() - run_date).days
                print(f"✅ Keeping: {dir_name} ({days_old} days old, {dir_size_mb:.1f} MB)")

        except Exception as e:
            error_msg = f"Error processing {run_dir.name}: {e}"
            print(f"❌ {error_msg}")
            errors.append(error_msg)

    freed_mb = freed_bytes / (1024 * 1024)

    print("=" * 80)
    if dry_run:
        print(f"\n📊 Dry run complete:")
        print(f"   Would delete: {deleted_count} directories")
        print(f"   Would free: {freed_mb:.1f} MB")
    else:
        print(f"\n📊 Cleanup complete:")
        print(f"   Deleted: {deleted_count} directories")
        print(f"   Freed: {freed_mb:.1f} MB")

    if errors:
        print(f"   Errors: {len(errors)}")
        for error in errors:
            print(f"     - {error}")

    return deleted_count, freed_mb, errors


if __name__ == "__main__":
    import sys

    # Check for dry-run flag
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("🔍 DRY RUN MODE - No files will be deleted\n")

    # Run cleanup
    deleted, freed_mb, errors = cleanup_old_runs(dry_run=dry_run)

    # Exit with error code if there were errors
    sys.exit(1 if errors else 0)
