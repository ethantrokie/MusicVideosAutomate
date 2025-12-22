import json
import os

base_path = "local_video_gen/wan_workflow_base.json"
output_path = "local_video_gen/wan_workflow_gguf.json"

with open(base_path, "r") as f:
    workflow = json.load(f)

nodes = workflow["nodes"]

for node in nodes:
    # 1. Modify UNET Loader (Node 37)
    if node["id"] == 37:
        print("Patching Node 37 (UNETLoader) -> UnetLoaderGGUF")
        node["type"] = "UnetLoaderGGUF"
        # GGUF loader usually takes filename as first widget.
        node["widgets_values"] = ["wan2.1-t2v-14b-Q4_K_M.gguf"]
        # Note: Depending on the node version, it might have other inputs? 
        # Standard UnetLoaderGGUF usually just needs config or infers it.
    
    # 2. Modify Prompt (Node 6)
    if node["id"] == 6:
        print("Patching Node 6 (Positive Prompt)")
        # We will leave a template string that our generator script can replace via API override
        # Or we can just set a default for now.
        # Actually using API format (prompt object), we override via dictionary key.
        # But this file is for the 'Saved Workflow' format (UI format).
        # We need the API format to submit to /prompt endpoint!
        pass

# The 'workflow' object we have here is the UI format (with pos, size, etc).
# To submit to API, we need the "prompt" format (key=id, value={inputs, class_type}).
# ComfyUI can save in API format, but we downloaded the UI format JSON.
# We need to CONVERT UI format to API format or rely on the script to do it?
# Actually, it's safer to have the API format JSON. 
# But we can try to "Create" the API format structure manually or assume standard mapping.
# Wait, ComfyUI UI format is NOT directly submittable to /prompt.
# Use `comfyui_to_python` or just construct the graph manually? 
# Or: Load this workflow into ComfyUI manually once, save as API format, then use that?
# I don't have GUI access.

# Solution:
# Construct the API JSON manually based on the UI nodes list.
# Usually: 
# output[id] = { "inputs": { ... }, "class_type": node["type"] }
# "inputs" are derived from "widgets_values" and "inputs" links.
# This is tricky to parse from UI JSON perfectly without logic.

# ALTERNATIVE:
# Just modify the JSON and ask the user to "Load" it? No, I need to run it via CLI.
# I will try to map it. 
# Node 37 inputs: none (loader).
# Node 38 inputs: none (loader).
# Node 40 inputs: none.
# Node 6 inputs: clip=link.

# Let's try to build the API payload directly in `generate_wan_gguf.py` instead of relying on this JSON file if parsing is hard.
# OR: Does the downloaded JSON contain an "api_format" section? No.
#
# Actually, for standard workflows, constructing the API dict is:
# prompt_api = {}
# for node in nodes:
#    idx = str(node["id"])
#    prompt_api[idx] = { "class_type": node["type"], "inputs": {} }
#    ... fill inputs from widgets_values and link sources.
#
# This is error prone.
# 
# NEW PLAN: 
# Use a provided python script that defines the workflow using wrapper objects, 
# OR define the API JSON manually node by node in python (e.g. `workflow = {}`).
# Given the small number of nodes (10), defining it in Python is SAFER and easier than parsing the UI JSON.
#
# I will create `generate_wan_gguf.py` that DEFINES the workflow dictionary directly.
# I will use the Node IDs from the base JSON as reference.

print("Skipping JSON patch. Strategies moved to generation script.")
