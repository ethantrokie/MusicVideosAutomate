import sys
import os

# Set paths to simulate ComfyUI running from its dir or knowing about it
comfy_path = os.path.abspath("local_video_gen/ComfyUI")
sys.path.insert(0, comfy_path)

import folder_paths

print("Registered keys:", list(folder_paths.folder_names_and_paths.keys()))
print("UNET search paths:", folder_paths.get_folder_paths("unet"))
print("Diffusion Models search paths:", folder_paths.get_folder_paths("diffusion_models"))

print("\nListing 'unet' files:")
files = folder_paths.get_filename_list("unet")
print(files)

target = "Wan2.1-T2V-14B-Q4_K_M.gguf"
print(f"\nResolving '{target}' in 'unet':")
path = folder_paths.get_full_path("unet", target)
print(f"Result: {path}")

if path is None:
    print("Checking case variants...")
    for f in files:
        if f.lower() == target.lower():
            print(f"Found match ignoring case: {f}")
            print(f"Path for that: {folder_paths.get_full_path('unet', f)}")
