from huggingface_hub import hf_hub_download
import shutil
import os

def download_model(repo_id, filename, target_dir):
    print(f"Downloading {filename} from {repo_id}...")
    file_path = hf_hub_download(repo_id=repo_id, filename=filename)
    target_path = os.path.join(target_dir, os.path.basename(filename))
    print(f"Moving to {target_path}...")
    shutil.copy(file_path, target_path)
    print("Done.")

# Ensure dirs exist
base_dir = "local_video_gen/ComfyUI/models"
os.makedirs(f"{base_dir}/unet", exist_ok=True)
os.makedirs(f"{base_dir}/text_encoders", exist_ok=True) # or clip
os.makedirs(f"{base_dir}/vae", exist_ok=True)

# 1. GGUF Model
download_model(
    "city96/Wan2.1-T2V-14B-gguf",
    "wan2.1-t2v-14b-Q4_K_M.gguf", # Lowercase correction
    f"{base_dir}/unet"
)

# 2. T5 Encoder (FP8)
download_model(
    "Comfy-Org/Wan_2.1_ComfyUI_repackaged",
    "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors", 
    f"{base_dir}/text_encoders"
)
# Note: hf_hub_download handles subfolders in filename by downloading to cache, 
# then we might need to be careful about the copy dest. 
# Actually hf_hub_download returns the absolute path in cache.
# But for "split_files/...", the cache path will reflect that structure? 
# No, it returns the file path.

# 3. VAE
download_model(
    "Comfy-Org/Wan_2.1_ComfyUI_repackaged",
    "split_files/vae/wan_2.1_vae.safetensors",
    f"{base_dir}/vae"
)
