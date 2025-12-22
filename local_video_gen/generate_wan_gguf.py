import argparse
import json
import urllib.request
import urllib.parse
import time
import subprocess
import sys
import os
import websocket # pip install websocket-client
import uuid

SERVER_ADDRESS = "127.0.0.1:8188"
COMFY_DIR = os.path.abspath("local_video_gen/ComfyUI")

def is_comfy_running():
    try:
        with urllib.request.urlopen(f"http://{SERVER_ADDRESS}/system_stats", timeout=1) as response:
            return response.status == 200
    except:
        return False

def start_comfy():
    if is_comfy_running():
        print("ComfyUI is already running.")
        return

    print("Starting ComfyUI server...")
    # Run in the background
    cmd = [sys.executable, "main.py", "--listen", "127.0.0.1", "--port", "8188"]
    
    # Redirect output to file or devnull to avoid cluttering current terminal? 
    # Or keep it for debug. Let's start it as Popen.
    # We must set CWD to ComfyUI dir
    subprocess.Popen(cmd, cwd=COMFY_DIR) #, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print("Waiting for ComfyUI to be ready...")
    for _ in range(30): # Wait up to 30s
        if is_comfy_running():
            print("ComfyUI is ready!")
            return
        time.sleep(1)
    
    raise RuntimeError("Timed out waiting for ComfyUI to start.")

def queue_prompt(workflow):
    p = {"prompt": workflow, "client_id": str(uuid.uuid4())}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(f"http://{SERVER_ADDRESS}/prompt", data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_history(prompt_id):
    with urllib.request.urlopen(f"http://{SERVER_ADDRESS}/history/{prompt_id}") as response:
        return json.loads(response.read())

def get_node_info(node_class):
    try:
        with urllib.request.urlopen(f"http://{SERVER_ADDRESS}/object_info/{node_class}") as response:
            return json.loads(response.read())
    except:
        return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--steps", type=int, default=15)
    args = parser.parse_args()

    # 1. Start Server
    start_comfy()

    # 2. Construct Workflow
    # Based on: text_to_video_wan.json from ComfyOrg, adapted for GGUF
    
    # Check if correct EmptyLatent node exists
    empty_latent_type = "EmptyHunyuanLatentVideo"
    if not get_node_info(empty_latent_type):
        print(f"Warning: {empty_latent_type} not found. Trying fallback 'EmptyLatentVideo'...")
        empty_latent_type = "EmptyLatentVideo" # From Kijai wrapper?
        if not get_node_info(empty_latent_type):
             raise RuntimeError("Could not find suitable Empty Latent Video node. (Checked EmptyHunyuanLatentVideo, EmptyLatentVideo)")

    print(f"Using Latent Node: {empty_latent_type}")

    workflow = {}

    # Node 1: UnetLoaderGGUF
    workflow["1"] = {
        "inputs": {
            "unet_name": "wan2.1-t2v-14b-Q4_K_M.gguf"
        },
        "class_type": "UnetLoaderGGUF",
        "_meta": {"title": "Unet Loader (GGUF)"}
    }

    # Node 2: CLIPLoader (for T5)
    workflow["2"] = {
        "inputs": {
            "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
            "type": "wan"
        },
        "class_type": "CLIPLoader",
        "_meta": {"title": "Load CLIP (T5)"}
    }

    # Node 3: VAELoader
    workflow["3"] = {
        "inputs": {
            "vae_name": "wan_2.1_vae.safetensors"
        },
        "class_type": "VAELoader",
        "_meta": {"title": "Load VAE"}
    }

    # Node 4: Positive Prompt
    workflow["4"] = {
        "inputs": {
            "text": args.prompt,
            "clip": ["2", 0]
        },
        "class_type": "CLIPTextEncode",
        "_meta": {"title": "Positive Prompt"}
    }

    # Node 5: Negative Prompt
    workflow["5"] = {
        "inputs": {
            "text": "Overexposure, static, blurred details, subtitles, paintings, pictures, still, overall gray, worst quality, low quality, JPEG compression residue, ugly, mutilated, redundant fingers, poorly painted hands, poorly painted faces, deformed, disfigured, deformed limbs, fused fingers, cluttered background, three legs, a lot of people in the background, upside down",
            "clip": ["2", 0]
        },
        "class_type": "CLIPTextEncode",
        "_meta": {"title": "Negative Prompt"}
    }
    
    # Node 6: Empty Latent
    # Wan 2.1 480p is 832x480.
    workflow["6"] = {
        "inputs": {
            "width": 832,
            "height": 480,
            "length": 33, # 33 frames is standard for ~2s? or 5s?
            "batch_size": 1
        },
        "class_type": empty_latent_type,
        "_meta": {"title": "Empty Latent"}
    }

    # Node 7: KSampler
    workflow["7"] = {
        "inputs": {
            "seed": 42, # Fixed seed for testing
            "steps": args.steps,
            "cfg": 6.0,
            "sampler_name": "uni_pc",
            "scheduler": "simple",
            "denoise": 1.0,
            "model": ["1", 0],
            "positive": ["4", 0],
            "negative": ["5", 0],
            "latent_image": ["6", 0]
        },
        "class_type": "KSampler",
        "_meta": {"title": "KSampler"}
    }

    # Node 8: VAE Decode
    workflow["8"] = {
        "inputs": {
            "samples": ["7", 0],
            "vae": ["3", 0]
        },
        "class_type": "VAEDecode",
        "_meta": {"title": "VAE Decode"}
    }

    # Node 9: Save Video
    # SaveAnimatedWEBP or standard SaveImage if multiple frames?
    # Kijai wrapper has `SaveVideo`? Standard Comfy has `SaveAnimatedWEBP`.
    workflow["9"] = {
        "inputs": {
            "filename_prefix": "WanGen_GGUF",
            "fps": 16,
            "lossless": False,
            "quality": 90,
            "method": "default",
            "images": ["8", 0]
        },
        "class_type": "SaveAnimatedWEBP",
        "_meta": {"title": "Save WebP"}
    }

    # 3. Submit
    print("Submitting workflow...")
    # Clean up any previous 'WanGen_GGUF' files in output to find the new one easily
    output_dir = os.path.join(COMFY_DIR, "output")
    
    try:
        resp = queue_prompt(workflow)
        prompt_id = resp['prompt_id']
        print(f"Prompt ID: {prompt_id}")
    except urllib.error.HTTPError as e:
        print(f"Failed to queue prompt: {e}")
        print(e.read().decode())
        return

    # 4. Wait for completion
    ws = websocket.WebSocket()
    ws.connect(f"ws://{SERVER_ADDRESS}/ws?clientId={resp['prompt_id']}") # Should use client ID from queue?
    # Actually client_id needs to be tracked.
    
    print("Generating...")
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    print("Execution complete!")
                    break
                elif data['node']:
                    print(f"Executing node: {data['node']}")
        else:
            continue
            
    # 5. Find Output
    # We look for the most recent file matching 'WanGen_GGUF'
    files = [f for f in os.listdir(output_dir) if f.startswith("WanGen_GGUF")]
    if not files:
        print("Error: No output file found.")
        return
        
    latest_file = max([os.path.join(output_dir, f) for f in files], key=os.path.getctime)
    destination = os.path.abspath(args.output)
    
    print(f"Saving to {destination}...")
    # If the output is .webp and user asked for .mp4, we might need conversion or just rename if they accept webp.
    # The node creates WEBP.
    # If user wants MP4, we can use ffmpeg.
    # Check extension
    if destination.endswith(".mp4") and latest_file.endswith(".webp"):
        # Convert
        print("Converting WebP to MP4...")
        subprocess.run(["ffmpeg", "-y", "-i", latest_file, "-c:v", "libx264", "-pix_fmt", "yuv420p", destination], check=True)
    else:
        # Copy
        subprocess.run(["cp", latest_file, destination])
        
    print(f"Done! Saved to {destination}")

if __name__ == "__main__":
    main()
