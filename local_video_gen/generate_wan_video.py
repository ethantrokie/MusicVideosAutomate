import torch
from diffusers import WanPipeline
from diffusers.utils import export_to_video
import argparse
import os

def generate_video(prompt, output_path, num_inference_steps=50):
    """
    Generates a video using Wan 2.1 T2V-1.3B on Mac Silicon.
    """
    model_id = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"
    print(f"Initializing {model_id} for prompt: '{prompt}'")
    
    # Wan 2.1 1.3B is small enough to load in FP16 on 48GB RAM easily.
    # It might even run in FP32, but FP16 is faster and sufficient.
    pipe = WanPipeline.from_pretrained(
        model_id,
        torch_dtype=torch.float16
    )

    # QUANTIZATION: Use optimum-quanto to reduce memory usage on MPS
    # This effectively compresses weights to INT8, significantly reducing VRAM.
    from optimum.quanto import freeze, qint8, quantize
    
    print("Quantizing model to INT8 (weights only)...")
    # Quantize the heavy components
    quantize(pipe.transformer, weights=qint8)
    quantize(pipe.text_encoder, weights=qint8)
    quantize(pipe.vae, weights=qint8)
    
    # Freeze to bake in the quantization
    freeze(pipe.transformer)
    freeze(pipe.text_encoder)
    freeze(pipe.vae)
    print("Quantization complete.")

    # Freeze to bake in the quantization
    freeze(pipe.transformer)
    freeze(pipe.text_encoder)
    freeze(pipe.vae)
    print("Quantization complete.")

    # MANUAL SPLIT: T5 on CPU, Transformer on MPS
    # The crash happens because T5 tries to allocate 51GB on MPS.
    # We must compute text embeddings on CPU, then pass them to the GPU model.
    
    print("Moving Transformer/VAE to MPS (Int8)...")
    pipe.transformer.to("mps")
    pipe.vae.to("mps")
    
    # Force T5 to stay on CPU
    pipe.text_encoder.to("cpu")
    print("Kept Text Encoder on CPU to avoid OOM.")

    print("Encoding prompt on CPU...")
    # Manually encode prompt on CPU to avoid MPS allocation
    with torch.no_grad():
       prompt_embeds, negative_prompt_embeds = pipe.encode_prompt(
           prompt=prompt,
           device="cpu", # Crucial: Compute on CPU
           num_videos_per_prompt=1,
           do_classifier_free_guidance=True
       )
   
    # Move to MPS
    print("Moving embeddings to MPS...")
    prompt_embeds = prompt_embeds.to("mps")
    negative_prompt_embeds = negative_prompt_embeds.to("mps")
    
    # CRITICAL FIX: Force the pipeline to believe it's on MPS.
    # Otherwise, because text_encoder is on CPU, it generates CPU latents, crashing the GPU model.
    pipe._execution_device = torch.device("mps")
    
    print("Starting generation on MPS...")
    
    # Pass pre-computed embeddings. The pipeline handles moving them to MPS if needed.
    output = pipe(
        prompt_embeds=prompt_embeds,
        negative_prompt_embeds=negative_prompt_embeds,
        num_inference_steps=num_inference_steps,
        guidance_scale=5.0
    )
    
    video = output.frames[0]

    print("Generation complete. Saving video...")
    export_to_video(video, output_path, fps=15) # Wan usually defaults to 15 or 24
    print(f"Video saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate video using Wan 2.1 on Mac")
    parser.add_argument("--prompt", type=str, required=True, help="Text prompt for video generation")
    parser.add_argument("--output", type=str, default="output_wan.mp4", help="Output file path")
    parser.add_argument("--steps", type=int, default=50, help="Number of inference steps")
    
    args = parser.parse_args()
    
    generate_video(args.prompt, args.output, num_inference_steps=args.steps)
