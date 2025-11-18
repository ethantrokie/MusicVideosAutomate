"""
Output directory helper for timestamped runs.
Provides functions to get the correct output directory path.
"""

import os
from pathlib import Path


def get_output_dir() -> Path:
    """
    Get the output directory for the current pipeline run.

    Returns:
        Path to output directory (timestamped run dir or default 'outputs/')
    """
    # Check if running within pipeline (has OUTPUT_DIR env var)
    output_dir = os.getenv('OUTPUT_DIR')

    if output_dir:
        return Path(output_dir)
    else:
        # Fallback to 'outputs/' for backward compatibility or standalone runs
        return Path('outputs')


def get_output_path(filename: str) -> Path:
    """
    Get full path for an output file.

    Args:
        filename: Filename relative to output directory (e.g., 'research.json', 'media/shot_01.mp4')

    Returns:
        Full path to the file
    """
    return get_output_dir() / filename


def ensure_output_dir(subdir: str = None) -> Path:
    """
    Ensure output directory (and optional subdirectory) exists.

    Args:
        subdir: Optional subdirectory name (e.g., 'media', 'temp_media')

    Returns:
        Path to the directory
    """
    if subdir:
        path = get_output_dir() / subdir
    else:
        path = get_output_dir()

    path.mkdir(parents=True, exist_ok=True)
    return path


def get_run_timestamp() -> str:
    """
    Get the current run timestamp.

    Returns:
        Timestamp string (e.g., '20241116_143025') or 'standalone'
    """
    return os.getenv('RUN_TIMESTAMP', 'standalone')


def get_current_run_dir() -> Path:
    """
    Get the 'current' symlink path for easy access to latest run.

    Returns:
        Path to outputs/current (symlink to latest run)
    """
    return Path('outputs/current')
