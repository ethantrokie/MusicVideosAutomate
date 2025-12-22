#!/usr/bin/env python3
"""
Semantic video-to-phrase matching using CLIP + keyword boosting.
"""

import logging
from typing import List, Dict
import numpy as np
from sentence_transformers import SentenceTransformer


class SemanticMatcher:
    """Matches videos to phrase groups using CLIP embeddings and keyword boosting."""

    def __init__(self, model_name: str = 'clip-ViT-B-32', keyword_boost: float = 2.0):
        """
        Initialize semantic matcher.

        Args:
            model_name: CLIP model to use
            keyword_boost: Multiplier for keyword matches
        """
        self.model = SentenceTransformer(model_name)
        self.keyword_boost = keyword_boost
        self.logger = logging.getLogger(__name__)
        self.recent_videos = []  # Track recent uses for diversity

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def match_videos_to_groups(self, phrase_groups: List[Dict], available_media: List[Dict]) -> List[Dict]:
        """
        Assign best video to each phrase group using CLIP + keyword boosting.

        Args:
            phrase_groups: List of phrase group dicts
            available_media: List of video dicts with url, description

        Returns:
            phrase_groups with added video_url and match_score
        """
        if not phrase_groups or not available_media:
            return phrase_groups

        # Generate embeddings for all videos
        # Prefer enhanced_description from video LLM analysis if available
        video_texts = [
            v.get("enhanced_description") or v.get("description", "")
            for v in available_media
        ]
        video_embeddings = self.model.encode(video_texts, convert_to_numpy=True, show_progress_bar=False)

        matched_groups = []

        for group in phrase_groups:
            # Combine topic and phrases for semantic matching
            group_text = f"{group['topic']}. " + " ".join([p["text"] for p in group["phrases"]])
            group_embedding = self.model.encode([group_text], convert_to_numpy=True, show_progress_bar=False)[0]

            # Calculate base scores
            scores = []
            for i, video in enumerate(available_media):
                base_score = self.cosine_similarity(group_embedding, video_embeddings[i])

                # Apply keyword boosting (check both original and enhanced descriptions)
                video_desc_lower = (
                    video.get("enhanced_description", "") + " " + video.get("description", "")
                ).lower()
                boost = 1.0
                for key_term in group.get("key_terms", []):
                    if key_term.lower() in video_desc_lower:
                        boost *= self.keyword_boost

                final_score = base_score * boost

                # Apply diversity penalty for recently used videos
                if video["url"] in self.recent_videos:
                    penalty = 0.1 * self.recent_videos.count(video["url"])
                    final_score -= penalty

                scores.append((final_score, video))

            # Select best match
            scores.sort(key=lambda x: x[0], reverse=True)
            best_score, best_video = scores[0]

            # Check if this is continuation of same topic
            allow_reuse = False
            if matched_groups and matched_groups[-1].get("topic") == group["topic"]:
                allow_reuse = True

            if not allow_reuse:
                # Track for diversity (keep last 3)
                self.recent_videos.append(best_video["url"])
                if len(self.recent_videos) > 3:
                    self.recent_videos.pop(0)

            # Add match info to group
            group_with_match = group.copy()
            group_with_match["video_url"] = best_video["url"]
            group_with_match["video_description"] = best_video["description"]
            group_with_match["match_score"] = float(best_score)

            matched_groups.append(group_with_match)

            self.logger.info(f"Group {group['group_id']} '{group['topic'][:30]}...' → {best_video['url']} (score: {best_score:.3f})")

        return matched_groups
