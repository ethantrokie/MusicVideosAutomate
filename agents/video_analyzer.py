"""
Video Analyzer using MLX-VLM for educational content creation.
Runs locally on Mac M4 with Apple Silicon.
"""
import subprocess
import sys
from pathlib import Path


def analyze_video(
    video_path: str,
    prompt: str = "Describe this video in detail for educational purposes",
    model: str = "mlx-community/Qwen3-VL-8B-Instruct-4bit",
    max_tokens: int = 500,
    fps: float = 1.0,
) -> str:
    """
    Analyze a video using MLX-VLM.
    
    Args:
        video_path: Path to the video file
        prompt: Question or instruction for the model
        model: Hugging Face model identifier
        max_tokens: Maximum tokens in response
        fps: Frames per second to sample from video
    
    Returns:
        Model's text response about the video
    """
    cmd = [
        sys.executable, "-m", "mlx_vlm.video_generate",
        "--model", model,
        "--prompt", prompt,
        "--video", video_path,
        "--max-tokens", str(max_tokens),
        "--fps", str(fps),
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"Video analysis failed: {result.stderr}")
    
    # Parse the output to extract the response
    output = result.stdout
    if "==========\nFiles:" in output:
        # Extract text between the prompt and stats
        parts = output.split("==========")
        if len(parts) >= 3:
            response = parts[1].strip()
            # Remove the "Files:" and "Prompt:" sections
            lines = response.split("\n")
            response_lines = []
            capture = False
            for line in lines:
                if line.startswith("assistant"):
                    capture = True
                    continue
                if capture:
                    response_lines.append(line)
            return "\n".join(response_lines).strip()
    
    return output


def generate_educational_summary(video_path: str, model: str = "mlx-community/Qwen3-VL-8B-Instruct-4bit") -> dict:
    """
    Generate a comprehensive educational summary of a video.
    
    Returns a dictionary with key educational components.
    """
    prompts = {
        "main_topic": "What is the main topic or subject of this video? Be specific and concise.",
        "key_facts": "List 3-5 key educational facts or concepts shown in this video as bullet points.",
        "visual_elements": "Describe the important visual elements that help explain the topic.",
        "suggested_narration": "Write a brief educational narration script (2-3 sentences) for this video segment."
    }
    
    results = {}
    for key, prompt in prompts.items():
        print(f"Analyzing: {key}...")
        results[key] = analyze_video(video_path, prompt, model=model)
    
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python video_analyzer.py <video_path> [prompt]")
        print("\nExample:")
        print("  python video_analyzer.py my_video.mp4")
        print("  python video_analyzer.py my_video.mp4 'What is happening in this video?'")
        sys.exit(1)
    
    video_path = sys.argv[1]
    prompt = sys.argv[2] if len(sys.argv) > 2 else "Describe this video in detail for educational purposes"
    
    print(f"Analyzing video: {video_path}")
    print(f"Prompt: {prompt}")
    print("-" * 50)
    
    result = analyze_video(video_path, prompt)
    print(result)
