#!/usr/bin/env python3
"""Generate video descriptions using video LLM analysis."""

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


def generate_description(video_path: str, platform: str, topic: str = None) -> str:
    """Generate platform-specific description using video LLM.
    
    Args:
        video_path: Path to video file
        platform: Target platform (youtube, tiktok)
        topic: Optional topic hint from research
        
    Returns:
        Generated description text
    """
    topic_hint = f" about {topic}" if topic else ""
    
    if platform == "youtube":
        prompt = f"""Write a YouTube video description for this educational video{topic_hint}.

Include:
1. A hook sentence (what viewers will learn)
2. Key topics covered (2-3 bullet points)  
3. A call to action (like, subscribe)

Keep it under 150 words. Make it engaging and informative."""
    else:  # tiktok
        prompt = f"""Write a short TikTok caption for this educational video{topic_hint}.

Make it:
- Catchy and curiosity-inducing
- Include 3-5 relevant hashtags
- Under 50 words

Example format: "Did you know [hook]? 🤯 #education #science #fyp\""""

    python_path = get_video_llm_venv()
    
    cmd = [
        python_path, "-m", "mlx_vlm.video_generate",
        "--model", "mlx-community/Qwen3-VL-8B-Instruct-4bit",
        "--prompt", prompt,
        "--video", video_path,
        "--max-tokens", "250",
        "--fps", "0.5"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        
        if result.returncode == 0:
            # Parse the output to extract the response
            output = result.stdout
            
            # Try to extract just the generated text (after the prompt echo)
            if "assistant" in output.lower():
                # Find content after "assistant" marker
                parts = output.split("assistant")
                if len(parts) > 1:
                    return parts[-1].strip().strip("\n=")
            
            # Fallback: return cleaned output
            # Remove common MLX-VLM output artifacts
            cleaned = output.strip()
            # Remove stats lines
            lines = [l for l in cleaned.split("\n") 
                    if not l.startswith("Prompt:") 
                    and not l.startswith("Generation:")
                    and not l.startswith("Peak memory:")
                    and not l.startswith("=====")]
            return "\n".join(lines).strip()
    except subprocess.TimeoutExpired:
        print("  ⏱️ Timeout during generation")
    except Exception as e:
        print(f"  ⚠️ Error: {e}")
    
    return ""


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate video descriptions')
    parser.add_argument("--video", default="full", 
                       help="Video type: full, short_hook, short_educational")
    parser.add_argument("--platform", default="youtube", 
                       choices=["youtube", "tiktok"],
                       help="Platform: youtube, tiktok")
    args = parser.parse_args()
    
    # Find video file
    video_path = get_output_path(f"{args.video}.mp4")
    if not video_path.exists():
        print(f"❌ Video not found: {video_path}")
        sys.exit(1)
    
    # Try to get topic from research
    topic = None
    research_path = get_output_path("research.json")
    if research_path.exists():
        try:
            with open(research_path) as f:
                research = json.load(f)
            topic = research.get("topic", research.get("video_title"))
        except Exception:
            pass
    
    print(f"📝 Generating {args.platform} description for {args.video}...")
    if topic:
        print(f"   Topic: {topic}")
    
    description = generate_description(str(video_path), args.platform, topic)
    
    if description:
        # Save to file
        desc_file = get_output_path(f"description_{args.video}_{args.platform}.txt")
        with open(desc_file, "w") as f:
            f.write(description)
        
        print(f"✅ Description saved to {desc_file}")
        print(f"\n--- Generated Description ---\n{description}\n")
        sys.exit(0)
    else:
        print("❌ Failed to generate description")
        sys.exit(1)


if __name__ == "__main__":
    main()
