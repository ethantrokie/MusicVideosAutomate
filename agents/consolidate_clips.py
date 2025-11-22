#!/usr/bin/env python3
"""
Clip consolidation logic for merging phrase groups into longer video segments.
"""

from typing import List, Dict


def calculate_topic_similarity(group1: Dict, group2: Dict) -> float:
    """
    Calculate semantic similarity between two phrase groups.

    Args:
        group1: First phrase group with key_terms
        group2: Second phrase group with key_terms

    Returns:
        Similarity score between 0.0 and 1.0
    """
    terms1 = set(group1.get("key_terms", []))
    terms2 = set(group2.get("key_terms", []))

    if not terms1 or not terms2:
        return 0.0

    # Jaccard similarity: intersection / union
    intersection = len(terms1 & terms2)
    union = len(terms1 | terms2)

    return intersection / union if union > 0 else 0.0


def consolidate_phrase_groups(phrase_groups: List[Dict], config: Dict) -> List[Dict]:
    """
    Consolidate consecutive phrase groups into longer video clips.

    Args:
        phrase_groups: List of phrase group dicts with timing and topics
        config: Consolidation config with target/min/max durations

    Returns:
        List of consolidated clip dicts, each containing multiple phrase groups
    """
    if not phrase_groups:
        return []

    target_duration = config["target_clip_duration"]
    min_duration = config["min_clip_duration"]
    max_duration = config["max_clip_duration"]
    coherence_threshold = config["semantic_coherence_threshold"]

    consolidated = []
    current_clip = {
        "clip_id": 1,
        "phrase_groups": [phrase_groups[0]],
        "start_time": phrase_groups[0]["start_time"],
        "end_time": phrase_groups[0]["end_time"],
        "duration": phrase_groups[0]["duration"],
        "topics": [phrase_groups[0]["topic"]],
        "key_terms": phrase_groups[0].get("key_terms", [])
    }

    for i in range(1, len(phrase_groups)):
        group = phrase_groups[i]
        current_duration = current_clip["duration"]

        # Calculate if adding this group would exceed max duration
        potential_duration = group["end_time"] - current_clip["start_time"]

        # Check semantic similarity with current clip
        similarity = calculate_topic_similarity(
            {"key_terms": current_clip["key_terms"]},
            group
        )

        # Decision: merge or start new clip
        should_merge = (
            # Under target duration - always try to merge
            (current_duration < target_duration and similarity >= coherence_threshold)
            # Or under min duration - must merge regardless of similarity
            or (current_duration < min_duration)
        ) and potential_duration <= max_duration

        if should_merge:
            # Merge into current clip
            current_clip["phrase_groups"].append(group)
            current_clip["end_time"] = group["end_time"]
            current_clip["duration"] = current_clip["end_time"] - current_clip["start_time"]
            current_clip["topics"].append(group["topic"])

            # Add unique key terms
            for term in group.get("key_terms", []):
                if term not in current_clip["key_terms"]:
                    current_clip["key_terms"].append(term)
        else:
            # Start new clip
            consolidated.append(current_clip)

            current_clip = {
                "clip_id": len(consolidated) + 1,
                "phrase_groups": [group],
                "start_time": group["start_time"],
                "end_time": group["end_time"],
                "duration": group["duration"],
                "topics": [group["topic"]],
                "key_terms": group.get("key_terms", [])
            }

    # Add final clip
    consolidated.append(current_clip)

    return consolidated
