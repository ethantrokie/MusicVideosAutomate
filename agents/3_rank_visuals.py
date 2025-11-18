#!/usr/bin/env python3
"""
Visual Ranking Agent: Ranks media by visual diversity and relevance.
Uses CLIP embeddings and MMR algorithm to select diverse video candidates.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import requests
from PIL import Image
from io import BytesIO
from sentence_transformers import SentenceTransformer

# Add agents directory to path
sys.path.insert(0, str(Path(__file__).parent))
from output_helper import get_output_path, ensure_output_dir


class VisualRanker:
    """Ranks videos by visual diversity using CLIP embeddings and MMR."""

    def __init__(self, model_name: str = 'clip-ViT-B-32', lambda_param: float = 0.7):
        """
        Initialize the visual ranker.

        Args:
            model_name: CLIP model to use
            lambda_param: MMR balance (0-1). Higher = prioritize relevance over diversity
        """
        self.logger = logging.getLogger(__name__)
        self.model = SentenceTransformer(model_name)
        self.lambda_param = lambda_param

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def _download_thumbnail(self, url: str, timeout: int = 10) -> Image.Image:
        """
        Download thumbnail from URL.

        Args:
            url: Thumbnail URL
            timeout: Request timeout in seconds

        Returns:
            PIL Image or None if failed
        """
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                return Image.open(BytesIO(response.content)).convert('RGB')
        except Exception as e:
            self.logger.warning(f"Failed to download thumbnail from {url}: {e}")
        return None

    def _download_thumbnails_parallel(self, candidates: List[Dict], max_workers: int = 10) -> Tuple[List[Image.Image], List[Dict], List[Dict]]:
        """
        Download thumbnails in parallel for faster processing.

        Args:
            candidates: List of media candidates with thumbnail_url
            max_workers: Number of parallel download threads

        Returns:
            Tuple of (images, valid_candidates, failed_candidates)
        """
        images = []
        valid_candidates = []
        failed_candidates = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_candidate = {
                executor.submit(self._download_thumbnail, c.get('thumbnail_url', c['url'])): c
                for c in candidates
            }

            for future in as_completed(future_to_candidate):
                candidate = future_to_candidate[future]
                try:
                    image = future.result()
                    if image:
                        images.append(image)
                        valid_candidates.append(candidate)
                    else:
                        # Track failed downloads to append later
                        failed_candidates.append(candidate)
                except Exception as e:
                    self.logger.error(f"Thumbnail download failed for {candidate.get('url')}: {e}")
                    failed_candidates.append(candidate)

        return images, valid_candidates, failed_candidates

    def _encode_images(self, images: List[Image.Image]) -> np.ndarray:
        """
        Generate CLIP embeddings for images.

        Args:
            images: List of PIL Images

        Returns:
            numpy array of shape (n_images, embedding_dim)
        """
        return self.model.encode(images, convert_to_numpy=True, show_progress_bar=False)

    def _encode_texts(self, texts: List[str]) -> np.ndarray:
        """
        Generate CLIP embeddings for text descriptions.

        Args:
            texts: List of text strings

        Returns:
            numpy array of shape (n_texts, embedding_dim)
        """
        return self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

    def _calculate_mmr_scores(
        self,
        image_embeddings: np.ndarray,
        fact_embeddings: np.ndarray,
        candidates: List[Dict]
    ) -> List[Dict]:
        """
        Apply Maximal Marginal Relevance algorithm.

        Args:
            image_embeddings: CLIP embeddings for candidate images
            fact_embeddings: CLIP embeddings for key facts
            candidates: Original candidate dicts

        Returns:
            Ranked list of candidates with scores
        """
        n_candidates = len(candidates)
        selected_indices = []
        remaining_indices = list(range(n_candidates))

        # For each fact, select best diverse candidate
        for fact_idx in range(min(len(fact_embeddings), n_candidates)):
            fact_emb = fact_embeddings[fact_idx]
            best_score = -float('inf')
            best_idx = None

            for idx in remaining_indices:
                # Relevance: similarity to current fact
                relevance = self.cosine_similarity(image_embeddings[idx], fact_emb)

                # Diversity: maximum similarity to already selected
                if selected_indices:
                    similarities = [
                        self.cosine_similarity(image_embeddings[idx], image_embeddings[sel_idx])
                        for sel_idx in selected_indices
                    ]
                    max_similarity = max(similarities)
                else:
                    max_similarity = 0

                # MMR score
                score = self.lambda_param * relevance - (1 - self.lambda_param) * max_similarity

                if score > best_score:
                    best_score = score
                    best_idx = idx

            if best_idx is not None:
                selected_indices.append(best_idx)
                remaining_indices.remove(best_idx)

        # Add remaining candidates in order of best average relevance
        for idx in remaining_indices:
            avg_relevance = np.mean([
                self.cosine_similarity(image_embeddings[idx], fact_emb)
                for fact_emb in fact_embeddings
            ])
            selected_indices.append(idx)

        # Build ranked results
        ranked = []
        for rank, idx in enumerate(selected_indices):
            candidate = candidates[idx].copy()
            candidate['rank'] = rank + 1
            candidate['visual_score'] = float(np.mean([
                self.cosine_similarity(image_embeddings[idx], fact_emb)
                for fact_emb in fact_embeddings
            ]))
            ranked.append(candidate)

        return ranked

    def rank_media(self, research_data: Dict) -> List[Dict]:
        """
        Rank media candidates by visual diversity and relevance.

        Args:
            research_data: Research JSON with media_suggestions and key_facts

        Returns:
            Ranked list of media candidates
        """
        candidates = research_data.get('media_suggestions', [])
        key_facts = research_data.get('key_facts', [])

        if not candidates:
            self.logger.warning("No media candidates to rank")
            return []

        if not key_facts:
            self.logger.warning("No key facts for relevance scoring")
            return candidates

        self.logger.info(f"Ranking {len(candidates)} media candidates against {len(key_facts)} facts")

        # Download thumbnails in parallel
        images, valid_candidates, failed_candidates = self._download_thumbnails_parallel(candidates)

        if not images:
            self.logger.error("Failed to download any thumbnails")
            return candidates

        self.logger.info(f"Successfully downloaded {len(images)} thumbnails")

        # Generate embeddings
        image_embeddings = self._encode_images(images)
        fact_embeddings = self._encode_texts(key_facts)

        # Apply MMR ranking
        ranked = self._calculate_mmr_scores(image_embeddings, fact_embeddings, valid_candidates)

        # Append failed candidates to end (unranked but present)
        for candidate in failed_candidates:
            candidate['rank'] = len(ranked) + 1
            candidate['visual_score'] = 0.0  # No score since no thumbnail
            ranked.append(candidate)

        return ranked


def main():
    """Main entry point for visual ranking agent."""
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger = logging.getLogger(__name__)

    # Load research data
    research_path = get_output_path('research.json')
    if not research_path.exists():
        logger.error(f"Research data not found at {research_path}")
        sys.exit(1)

    with open(research_path) as f:
        research_data = json.load(f)

    # Enrich media suggestions with thumbnail URLs
    from stock_photo_api import StockPhotoResolver
    resolver = StockPhotoResolver()
    media_suggestions = research_data.get('media_suggestions', [])
    enriched_media = resolver.enrich_with_thumbnails(media_suggestions)
    research_data['media_suggestions'] = enriched_media

    # Initialize ranker
    ranker = VisualRanker(lambda_param=0.7)

    # Rank media
    ranked_media = ranker.rank_media(research_data)

    # Save rankings
    output_path = get_output_path('visual_rankings.json')
    output_data = {
        'ranked_media': ranked_media,
        'metadata': {
            'total_analyzed': len(research_data.get('media_suggestions', [])),
            'ranking_method': 'mmr',
            'lambda': 0.7,
            'model': 'clip-ViT-B-32'
        }
    }

    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)

    logger.info(f"✅ Visual ranking complete: {output_path}")
    logger.info(f"   Ranked {len(ranked_media)} media items")


if __name__ == '__main__':
    main()
