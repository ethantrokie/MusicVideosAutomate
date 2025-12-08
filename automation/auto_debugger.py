#!/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/venv/bin/python3
"""
Auto-debugger for pipeline failures.
Uses Claude Code CLI to analyze errors and attempt fixes.
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime


def load_config():
    """Load automation configuration."""
    config_path = Path("automation/config/automation_config.json")
    with open(config_path) as f:
        return json.load(f)


def get_log_tail(log_file, lines=100):
    """Get the last N lines of a log file."""
    log_path = Path(log_file)
    if not log_path.exists():
        return "Log file not found"
    
    with open(log_path) as f:
        all_lines = f.readlines()
        return "".join(all_lines[-lines:])


def get_failed_stage_info(run_dir):
    """Analyze the failed run directory to determine what failed."""
    run_path = Path(run_dir)
    
    stages_status = {
        "research": run_path / "research.json",
        "visual_ranking": run_path / "visual_rankings.json",
        "lyrics": run_path / "lyrics.json",
        "music": run_path / "song.mp3",
        "segments": run_path / "segments.json",
        "media_curation": run_path / "approved_media.json",
        "video_assembly": run_path / "full.mp4",
        "subtitles": run_path / "subtitles",
        "upload": run_path / "video_id_full.txt",
    }
    
    completed = []
    failed_at = None
    
    for stage, artifact in stages_status.items():
        if artifact.exists():
            completed.append(stage)
        else:
            if failed_at is None:
                failed_at = stage
    
    return {
        "completed_stages": completed,
        "failed_at": failed_at or "unknown",
        "run_dir": str(run_dir)
    }


def run_claude_debugger(log_context, stage_info, project_dir):
    """Run Claude Code CLI to debug the issue."""
    
    prompt = f"""You are debugging a pipeline failure in an educational video automation system.

PROJECT DIRECTORY: {project_dir}

FAILED STAGE: {stage_info['failed_at']}
COMPLETED STAGES: {', '.join(stage_info['completed_stages']) or 'none'}
RUN DIRECTORY: {stage_info['run_dir']}

RECENT LOG OUTPUT (last 100 lines):
```
{log_context}
```

DEBUGGING INSTRUCTIONS:
1. Analyze the error in the log output
2. Identify the root cause of the failure
3. If it's a code bug that you can fix, make the fix
4. If it's an external issue (API timeout, network, etc.), report that you cannot fix it
5. If you made a fix, output exactly: FIX_APPLIED: [brief description]
6. If you cannot fix it, output exactly: CANNOT_FIX: [reason]

Focus on common issues:
- Python syntax errors or import issues
- Missing files or directories
- API configuration problems
- JSON parsing errors

DO NOT ask questions. Analyze and act. Output only the result line at the end."""

    debug_log = Path(f"automation/logs/debug_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.log")
    debug_log.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        result = subprocess.run(
            ["/Users/ethantrokie/.npm-global/bin/claude", "-p", prompt, "--model", "claude-sonnet-4-5", "--dangerously-skip-permissions"],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout for debugging
            cwd=project_dir
        )
        
        # Log the full output
        with open(debug_log, 'w') as f:
            f.write(f"=== Auto-Debug Session ===\n")
            f.write(f"Time: {datetime.now().isoformat()}\n")
            f.write(f"Failed Stage: {stage_info['failed_at']}\n")
            f.write(f"Run Dir: {stage_info['run_dir']}\n\n")
            f.write(f"=== Claude Output ===\n")
            f.write(result.stdout)
            if result.stderr:
                f.write(f"\n=== Stderr ===\n{result.stderr}")
        
        if result.returncode != 0:
            return False, f"Claude CLI failed: {result.stderr}", str(debug_log)
        
        output = result.stdout.strip()
        
        # Check for fix status
        if "FIX_APPLIED:" in output:
            fix_desc = output.split("FIX_APPLIED:")[-1].strip().split("\n")[0]
            return True, fix_desc, str(debug_log)
        elif "CANNOT_FIX:" in output:
            reason = output.split("CANNOT_FIX:")[-1].strip().split("\n")[0]
            return False, reason, str(debug_log)
        else:
            return False, "No clear fix status in output", str(debug_log)
            
    except subprocess.TimeoutExpired:
        return False, "Debugging timed out after 5 minutes", str(debug_log)
    except Exception as e:
        return False, f"Unexpected error: {e}", str(debug_log)


def send_notification(message):
    """Send notification via the notification helper."""
    subprocess.run(
        ["./automation/notification_helper.sh", message],
        capture_output=True
    )


def main():
    """Main execution."""
    if len(sys.argv) < 3:
        print("Usage: auto_debugger.py <failed_run_dir> <log_file>")
        sys.exit(1)
    
    failed_run_dir = sys.argv[1]
    log_file = sys.argv[2]
    project_dir = Path(__file__).parent.parent.absolute()
    
    print("🔧 Auto-debugger starting...")
    
    # Check if auto-debug is enabled
    config = load_config()
    auto_debug_config = config.get("auto_debug", {"enabled": True, "max_attempts": 1})
    
    if not auto_debug_config.get("enabled", True):
        print("Auto-debug is disabled in config")
        sys.exit(0)
    
    # Get context for debugging
    log_context = get_log_tail(log_file)
    stage_info = get_failed_stage_info(failed_run_dir)
    
    print(f"  Failed at stage: {stage_info['failed_at']}")
    print(f"  Completed: {', '.join(stage_info['completed_stages']) or 'none'}")
    print("  Invoking Claude Code for debugging...")
    
    # Run Claude to debug
    fixed, message, debug_log = run_claude_debugger(log_context, stage_info, str(project_dir))
    
    if fixed:
        print(f"✅ Fix applied: {message}")
        print(f"  Debug log: {debug_log}")
        
        # Attempt to resume the pipeline
        print("  Attempting to resume pipeline...")
        run_dir_name = Path(failed_run_dir).name
        
        result = subprocess.run(
            ["./pipeline.sh", f"--resume={run_dir_name}", "--express"],
            capture_output=True,
            text=True,
            cwd=str(project_dir)
        )
        
        if result.returncode == 0:
            send_notification(f"🔧 Auto-debug fixed pipeline!\nFix: {message}\nPipeline resumed successfully.")
            print("✅ Pipeline resumed successfully!")
            sys.exit(0)
        else:
            send_notification(f"🔧 Auto-debug applied fix but pipeline still failed.\nFix: {message}\nCheck debug log: {debug_log}")
            print("❌ Pipeline still failed after fix")
            sys.exit(1)
    else:
        print(f"❌ Could not auto-fix: {message}")
        print(f"  Debug log: {debug_log}")
        send_notification(f"🔧 Auto-debug could not fix pipeline.\nReason: {message}\nDebug log: {debug_log}")
        sys.exit(1)


if __name__ == "__main__":
    main()
