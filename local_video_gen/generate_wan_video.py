import torch
from diffusers import WanPipeline
from diffusers.utils import export_to_video
import argparse


def generate_video(prompt, output_path, num_inference_steps=50):
    """
    Generates a video using Wan 2.1 T2V-1.3B on Mac Silicon (M1/M2/M3/M4).
    Uses modern diffusers API with MPS backend.
    """
    model_id = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"

    # Determine device
    if torch.backends.mps.is_available():
        device = "mps"
        print(f"Using MPS (Apple Silicon GPU)")
    else:
        device = "cpu"
        print(f"MPS not available, using CPU")

    print(f"Initializing {model_id} for prompt: '{prompt}'")

    # Load pipeline in float16 for memory efficiency
    pipe = WanPipeline.from_pretrained(
        model_id,
        torch_dtype=torch.float16
    )

    # MPS on Mac has buffer size limits - fall back to CPU for large models
    # The transformer alone needs ~48GB which exceeds MPS limits
    print("Using CPU (MPS buffer too small for this model)")
    pipe.to("cpu")

    # Enable attention slicing for memory efficiency (recommended for <64GB RAM)
    pipe.enable_attention_slicing()
    print("Enabled attention slicing")

    # Optional: Enable VAE slicing/tiling for additional memory savings
    if hasattr(pipe, 'vae') and hasattr(pipe.vae, 'enable_slicing'):
        pipe.vae.enable_slicing()
        print("Enabled VAE slicing")
    if hasattr(pipe, 'vae') and hasattr(pipe.vae, 'enable_tiling'):
        pipe.vae.enable_tiling()
        print("Enabled VAE tiling")

    print(f"Starting generation with {num_inference_steps} steps...")

    # Generate video
    output = pipe(
        prompt=prompt,
        num_inference_steps=num_inference_steps,
        guidance_scale=5.0,
        num_frames=81,  # ~5 seconds at 16fps (must be 4k+1)
    )

    video = output.frames[0]

    print("Generation complete. Saving video...")
    export_to_video(video, output_path, fps=16)
    print(f"Video saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate video using Wan 2.1 on Mac")
    parser.add_argument("--prompt", type=str, required=True, help="Text prompt for video generation")
    parser.add_argument("--output", type=str, default="output_wan.mp4", help="Output file path")
    parser.add_argument("--steps", type=int, default=50, help="Number of inference steps")

    args = parser.parse_args()

    generate_video(args.prompt, args.output, num_inference_steps=args.steps)
