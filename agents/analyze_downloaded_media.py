#!/usr/bin/env python3
"""Analyze downloaded media clips using video LLM to generate rich descriptions."""

import json
import subprocess
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from output_helper import get_output_path


def get_video_llm_venv() -> str:
    """Get path to video LLM virtual environment."""
    project_root = Path(__file__).parent.parent
    venv_path = project_root / "venv_video_llm"
    if venv_path.exists():
        return str(venv_path / "bin" / "python")
    return sys.executable


def analyze_clip(video_path: str, topic: str) -> dict:
    """Analyze a single clip using MLX-VLM.
    
    Args:
        video_path: Path to video file
        topic: Educational topic for context
        
    Returns:
        Dict with enhanced_description and analysis_success
    """
    prompt = f"""Analyze this video clip for use in an educational video about: {topic}

Describe in 2-3 sentences:
1. Main visual content (what is shown)
2. Motion/dynamics and colors
3. How it relates to the educational topic

Keep response under 75 words."""

    python_path = get_video_llm_venv()
    
    cmd = [
        python_path, "-m", "mlx_vlm.video_generate",
        "--model", "mlx-community/Qwen3-VL-8B-Instruct-4bit",
        "--prompt", prompt,
        "--video", video_path,
        "--max-tokens", "100",
        "--fps", "1.0"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            output = result.stdout.strip()
            
            # Clean up output
            lines = [l for l in output.split("\n") 
                    if not l.startswith("Prompt:") 
                    and not l.startswith("Generation:")
                    and not l.startswith("Peak memory:")
                    and not l.startswith("=====")
                    and not l.startswith("Loading model:")
                    and not l.startswith("Fetching")]
            
            cleaned = "\n".join(lines).strip()
            
            # Extract text after assistant marker if present
            if "assistant" in cleaned.lower():
                parts = cleaned.split("assistant")
                if len(parts) > 1:
                    cleaned = parts[-1].strip()
            
            return {"enhanced_description": cleaned, "analysis_success": True}
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass
    
    return {"enhanced_description": "", "analysis_success": False}


def analyze_all_media(manifest: dict, topic: str) -> dict:
    """Analyze all downloaded media clips.
    
    Args:
        manifest: Media manifest with 'downloaded' list
        topic: Educational topic for context
        
    Returns:
        Updated manifest with enhanced descriptions
    """
    downloaded = manifest.get("downloaded", [])
    
    if not downloaded:
        return manifest
    
    print(f"🔍 Analyzing {len(downloaded)} clips with Video LLM...")
    print(f"   Topic: {topic}")
    
    success_count = 0
    
    for i, item in enumerate(downloaded):
        local_path = item.get("local_path", "")
        if not local_path or not Path(local_path).exists():
            print(f"  [{i+1}/{len(downloaded)}] ⚠️ Missing: {local_path}")
            continue
            
        filename = Path(local_path).name
        print(f"  [{i+1}/{len(downloaded)}] Analyzing {filename}...", end=" ", flush=True)
        
        try:
            analysis = analyze_clip(local_path, topic)
            item["enhanced_description"] = analysis.get("enhanced_description", "")
            item["analysis_success"] = analysis.get("analysis_success", False)
            
            if analysis["analysis_success"]:
                success_count += 1
                print("✅")
            else:
                print("⚠️")
        except Exception as e:
            item["enhanced_description"] = ""
            item["analysis_success"] = False
            print(f"❌ {e}")
    
    print(f"\n✅ Enhanced {success_count}/{len(downloaded)} clips")
    
    return manifest


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze downloaded media')
    parser.add_argument('--dry-run', action='store_true',
                       help='Analyze but do not save results')
    args = parser.parse_args()
    
    # Load existing manifest
    manifest_path = get_output_path("media_manifest.json")
    if not manifest_path.exists():
        print(f"❌ Media manifest not found: {manifest_path}")
        sys.exit(1)
    
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    # Load research for topic context
    topic = "educational content"
    research_path = get_output_path("research.json")
    if research_path.exists():
        try:
            with open(research_path) as f:
                research = json.load(f)
            topic = research.get("topic", topic)
        except Exception:
            pass
    
    # Analyze all clips
    updated_manifest = analyze_all_media(manifest, topic)
    
    if not args.dry_run:
        # Save enhanced manifest
        enhanced_path = get_output_path("media_manifest_enhanced.json")
        with open(enhanced_path, "w") as f:
            json.dump(updated_manifest, f, indent=2)
        print(f"\n📁 Enhanced manifest saved to {enhanced_path}")
        
        # Also update original for downstream compatibility
        with open(manifest_path, "w") as f:
            json.dump(updated_manifest, f, indent=2)
        print(f"📁 Original manifest updated")


if __name__ == "__main__":
    main()
