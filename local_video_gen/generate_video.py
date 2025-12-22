import torch
from diffusers import CogVideoXPipeline
from diffusers.utils import export_to_video
import argparse
import os

def generate_video(prompt, output_path, num_frames=49, guidance_scale=6.0, num_inference_steps=50):
    """
    Generates a video from a text prompt using CogVideoX on Mac Silicon.
    """
    # Use 2b by default as 5b requires >48GB RAM for attention
    model_name = "THUDM/CogVideoX-2b" 
    print(f"Initializing {model_name} for prompt: '{prompt}'")
    
    # Load the pipeline
    # We use torch.float16 for efficiency (T5-XXL is large)
    pipe = CogVideoXPipeline.from_pretrained(
        model_name,
        torch_dtype=torch.float16
    )

    # Memory optimization for Apple Silicon (M4 48GB)
    # The 2B model fits in RAM, so we can try running directly on MPS without offloading to avoid acceleration hooks bugs.

    print("Moving pipeline to MPS...")
    try:
        # Cast to float16 explicitly then move to MPS
        pipe.to(device="mps", dtype=torch.float16)
        print("Moved pipeline to MPS successfully (FP16).")
    except Exception as e:
        print(f"Error moving to MPS: {e}")
        exit(1)

    # 2. VAE Optimizations (Reduces memory during decoding)
    try:
        pipe.vae.enable_tiling()
        pipe.vae.enable_slicing()
        print("Enabled VAE slicing and tiling.")
    except Exception as e:
        print(f"Warning: VAE optimization failed: {e}")

    # 3. Attention Slicing
    try:
         pipe.enable_attention_slicing()
         print("Enabled attention slicing.")
    except Exception as e:
         print(f"Warning: Attention slicing not available on this pipeline version: {e}")

    
    # Optional: Scheduler configuration can be adjusted here if needed
    
    # Optional: Scheduler configuration can be adjusted here if needed
    
    print("Starting generation... (this may take several minutes)")
    
    video = pipe(
        prompt=prompt,
        num_videos_per_prompt=1,
        num_inference_steps=num_inference_steps,
        num_frames=num_frames,
        guidance_scale=guidance_scale,
        generator=torch.Generator("mps").manual_seed(42) # determinism
    ).frames[0]

    print("Generation complete. Saving video...")
    
    export_to_video(video, output_path, fps=8)
    print(f"Video saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate video using CogVideoX-2b on Mac")
    parser.add_argument("--prompt", type=str, required=True, help="Text prompt for video generation")
    parser.add_argument("--output", type=str, default="output.mp4", help="Output file path")
    parser.add_argument("--steps", type=int, default=50, help="Number of inference steps")
    parser.add_argument("--frames", type=int, default=49, help="Number of frames to generate (reduce to 33 or 17 for lower memory)")
    
    args = parser.parse_args()
    
    generate_video(args.prompt, args.output, num_inference_steps=args.steps, num_frames=args.frames)

