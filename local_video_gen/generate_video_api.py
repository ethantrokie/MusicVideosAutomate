import argparse
import os
import sys
import time
import requests
import replicate
from openai import OpenAI

# Model IDs
MODEL_WAN = "wavespeedai/wan-2.1-t2v-720p" # Best Performance (14B Pro)
MODEL_LTX = "lightricks/ltx-video"       # Draft / Speed

def generate_sora(prompt, output_file, api_key):
    """
    Generates video using OpenAI Sora 2 API.
    Flow: Create Job -> Poll Status -> Download Video
    """
    print(f"Initializing OpenAI client for Sora 2...")
    client = OpenAI(api_key=api_key)
    
    print(f"Submitting Sora 2 generation job for prompt: '{prompt}'...")
    # Note: Using the standard 'video.generations.create' endpoint pattern associated with Sora availability
    try:
        # Step 1: Create generation job
        # Syntax based on standard OpenAI beta/preview patterns for video
        # Adjust model name to "sora-2" or similar as per availability
        response = client.video.generations.create(
            model="sora-2", 
            prompt=prompt,
            quality="standard", # or "high" if supported
            response_format="url",
            size="1280x720"
        )
        
        # Check if response is immediate or job-based. 
        # Most video APIs are async. OpenAI's DALL-E is sync, but Sora is likely async.
        # If the SDK returns a job ID (generic object), we poll. 
        # Use simple attribute check.
        
        if hasattr(response, 'id') and not hasattr(response, 'data'):
            # It's an async job
            job_id = response.id
            print(f"Job started. ID: {job_id}")
            
            while True:
                job_status = client.video.generations.retrieve(job_id)
                status = job_status.status
                print(f"Status: {status}")
                
                if status == 'completed':
                    video_url = job_status.result.url # or job_status.data[0].url
                    break
                elif status == 'failed':
                    print(f"Generation failed: {job_status.error}")
                    sys.exit(1)
                elif status in ['cancelled', 'expired']:
                     print(f"Generation stopped: {status}")
                     sys.exit(1)
                
                time.sleep(5)
        elif hasattr(response, 'data'):
             # Sync response (like DALL-E) - unlikely for video but possible for short clips
             video_url = response.data[0].url
        else:
            # Fallback for unknown response structure
            print(f"Unknown response structure: {response}")
            sys.exit(1)
            
        print(f"Generation complete. Downloading from {video_url}...")
        download_video(video_url, output_file)

    except Exception as e:
        print(f"OpenAI API Error: {e}")
        print("Note: If 'video.generations' is not found, ensuring 'openai' lib is latest version.")
        sys.exit(1)

def generate_replicate(model_id, prompt, output_file):
    """
    Generates video using Replicate API (Wan 2.1 or LTX).
    """
    print(f"Submitting to Replicate ({model_id})...")
    try:
        if "ltx" in model_id:
             input_data = {"prompt": prompt}
        else:
             # Wan 2.1 specific
             input_data = {
                 "prompt": prompt,
                 "aspect_ratio": "16:9"
             }

        output = replicate.run(model_id, input=input_data)
        
        # Handle Output
        video_url = None
        if isinstance(output, str):
            video_url = output
        elif isinstance(output, list) and len(output) > 0:
            video_url = output[0]
        elif isinstance(output, dict) and "video" in output:
             video_url = output["video"]
        
        if not video_url:
            print("Error: Could not parse video URL from output.")
            sys.exit(1)
            
        print(f"Generation complete. Downloading from {video_url}...")
        download_video(video_url, output_file)

    except replicate.exceptions.ReplicateError as e:
        print(f"Replicate API Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected Error: {e}")
        sys.exit(1)

def download_video(url, filename):
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Saved to {filename}")
    else:
        print(f"Error downloading video: {response.status_code}")
        print(response.text)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Generate video using AI APIs (Sora 2, Wan 2.1, LTX)")
    parser.add_argument("--prompt", required=True, help="Text prompt for video generation")
    parser.add_argument("--output", required=True, help="Output filename (e.g. video.mp4)")
    parser.add_argument("--model", choices=["sora", "wan", "ltx"], default="sora", 
                      help="Model: 'sora' (OpenAI SOTA), 'wan' (Replicate High-Fidelity), 'ltx' (Replicate Draft)")
    args = parser.parse_args()

    print(f"Selected Model Strategy: {args.model.upper()}")
    print(f"Prompt: {args.prompt}")

    if args.model == "sora":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("Error: OPENAI_API_KEY environment variable is not set.")
            print("Please export it: export OPENAI_API_KEY=sk-...")
            sys.exit(1)
        generate_sora(args.prompt, args.output, api_key)
    
    elif args.model == "wan":
        check_replicate_token()
        generate_replicate(MODEL_WAN, args.prompt, args.output)
        
    elif args.model == "ltx":
        check_replicate_token()
        generate_replicate(MODEL_LTX, args.prompt, args.output)

def check_replicate_token():
    if not os.environ.get("REPLICATE_API_TOKEN"):
        print("Error: REPLICATE_API_TOKEN environment variable is not set.")
        print("Please export it: export REPLICATE_API_TOKEN=r8_...")
        sys.exit(1)

if __name__ == "__main__":
    main()
