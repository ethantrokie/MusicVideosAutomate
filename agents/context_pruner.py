import json
import os
import sys

def prune_context(target_agent):
    """
    Prunes the research and lyrics JSON files to create a smaller context for the target agent.
    """
    output_dir = os.getenv('OUTPUT_DIR', 'outputs/current')
    research_file = os.path.join(output_dir, 'research.json')

    if not os.path.exists(research_file):
        print(f"Error: {research_file} not found.")
        sys.exit(1)

    with open(research_file, 'r') as f:
        research_data = json.load(f)

    if target_agent == 'lyricist':
        pruned_data = {'key_facts': research_data.get('key_facts', [])}
        pruned_file = os.path.join(output_dir, 'research_pruned_for_lyrics.json')
    elif target_agent == 'curator':
        pruned_data = {'media_suggestions': research_data.get('media_suggestions', [])}
        pruned_file = os.path.join(output_dir, 'research_pruned_for_curator.json')
    else:
        print(f"Error: Invalid target agent '{target_agent}'.")
        sys.exit(1)

    with open(pruned_file, 'w') as f:
        json.dump(pruned_data, f, indent=2)

    print(f"Successfully created {pruned_file}")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python context_pruner.py <target_agent>")
        sys.exit(1)
    target_agent = sys.argv[1]
    prune_context(target_agent)
