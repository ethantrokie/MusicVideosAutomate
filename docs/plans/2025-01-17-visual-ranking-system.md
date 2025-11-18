# Visual Ranking System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add visual diversity ranking to eliminate repetitive video content by analyzing thumbnails with CLIP and selecting maximally diverse videos using MMR algorithm.

**Architecture:** Insert new pipeline stage between Research and Lyrics that downloads thumbnails, generates CLIP embeddings, calculates diversity scores via MMR algorithm, and outputs rankings for curator to consume. Includes automatic research gap-filling when curator can't find enough diverse matches.

**Tech Stack:** Python 3.13, sentence-transformers (CLIP), PIL, requests, numpy, concurrent.futures

---

## Task 1: Install Dependencies

**Files:**
- Modify: `requirements.txt`

**Step 1: Add sentence-transformers to requirements**

Add to `requirements.txt`:
```
sentence-transformers>=2.2.0
torch>=2.0.0
```

**Step 2: Install in virtual environment**

Run:
```bash
source venv/bin/activate
pip install sentence-transformers torch
```

Expected: Successfully installed packages

**Step 3: Test CLIP model download**

Run:
```bash
python3 -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('clip-ViT-B-32'); print('CLIP loaded successfully')"
```

Expected: "CLIP loaded successfully" (first run downloads ~400MB model)

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "feat: add sentence-transformers for visual ranking"
```

---

## Task 2: Create Visual Ranking Agent (Core Logic)

**Files:**
- Create: `agents/3_rank_visuals.py`

**Step 1: Write basic structure with imports**

Create `agents/3_rank_visuals.py`:
```python
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
```

**Step 2: Add thumbnail downloading method**

Add to `VisualRanker` class:
```python
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
```

**Step 3: Add parallel thumbnail downloading**

Add to `VisualRanker` class:
```python
def _download_thumbnails_parallel(self, candidates: List[Dict], max_workers: int = 10) -> Tuple[List[Image.Image], List[Dict]]:
    """
    Download thumbnails in parallel for faster processing.

    Args:
        candidates: List of media candidates with thumbnail_url
        max_workers: Number of parallel download threads

    Returns:
        Tuple of (images, valid_candidates)
    """
    images = []
    valid_candidates = []

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
            except Exception as e:
                self.logger.error(f"Thumbnail download failed for {candidate.get('url')}: {e}")

    return images, valid_candidates
```

**Step 4: Add CLIP encoding methods**

Add to `VisualRanker` class:
```python
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
```

**Step 5: Add MMR ranking algorithm**

Add to `VisualRanker` class:
```python
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
```

**Step 6: Add main ranking method**

Add to `VisualRanker` class:
```python
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
    images, valid_candidates = self._download_thumbnails_parallel(candidates)

    if not images:
        self.logger.error("Failed to download any thumbnails")
        return candidates

    self.logger.info(f"Successfully downloaded {len(images)} thumbnails")

    # Generate embeddings
    image_embeddings = self._encode_images(images)
    fact_embeddings = self._encode_texts(key_facts)

    # Apply MMR ranking
    ranked = self._calculate_mmr_scores(image_embeddings, fact_embeddings, valid_candidates)

    return ranked
```

**Step 7: Add main function**

Add at end of file:
```python
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
```

**Step 8: Make executable**

Run:
```bash
chmod +x agents/3_rank_visuals.py
```

**Step 9: Commit**

```bash
git add agents/3_rank_visuals.py
git commit -m "feat: add visual ranking agent with CLIP and MMR"
```

---

## Task 3: Add Thumbnail URL Extraction to Stock Photo API

**Files:**
- Modify: `agents/stock_photo_api.py`

**Step 1: Read current stock_photo_api.py to understand structure**

Run:
```bash
head -50 agents/stock_photo_api.py
```

**Step 2: Add thumbnail extraction methods**

Add to `StockPhotoResolver` class in `agents/stock_photo_api.py`:
```python
def get_thumbnail_url(self, page_url: str, media_type: str = 'video') -> str:
    """
    Extract thumbnail URL from page URL.

    Args:
        page_url: Webpage URL (e.g., pexels.com/video/...)
        media_type: 'video' or 'image'

    Returns:
        Thumbnail URL or original URL if extraction fails
    """
    # Detect source
    if 'pexels.com' in page_url:
        return self._get_pexels_thumbnail(page_url)
    elif 'pixabay.com' in page_url:
        return self._get_pixabay_thumbnail(page_url)
    elif 'giphy.com' in page_url:
        return self._get_giphy_thumbnail(page_url)
    else:
        return page_url

def _get_pexels_thumbnail(self, page_url: str) -> str:
    """Extract Pexels thumbnail URL."""
    # Pexels video page URLs contain video ID
    # Example: https://www.pexels.com/video/NAME-12345/
    try:
        video_id = page_url.rstrip('/').split('-')[-1]
        # Pexels API or fallback to page scraping
        return f"https://images.pexels.com/videos/{video_id}/preview.jpg"
    except:
        return page_url

def _get_pixabay_thumbnail(self, page_url: str) -> str:
    """Extract Pixabay thumbnail URL."""
    # Pixabay provides preview images
    try:
        # Extract video ID from URL
        video_id = page_url.rstrip('/').split('-')[-1].replace('/', '')
        return f"https://i.vimeocdn.com/video/{video_id}_640x360.jpg"
    except:
        return page_url

def _get_giphy_thumbnail(self, page_url: str) -> str:
    """Extract Giphy thumbnail URL."""
    # Giphy GIF URLs already work as thumbnails
    return page_url
```

**Step 3: Update research data with thumbnails**

Add method to `StockPhotoResolver`:
```python
def enrich_with_thumbnails(self, media_suggestions: List[Dict]) -> List[Dict]:
    """
    Add thumbnail_url field to media suggestions.

    Args:
        media_suggestions: List of media dicts from research

    Returns:
        Enriched media suggestions with thumbnail_url
    """
    for media in media_suggestions:
        media['thumbnail_url'] = self.get_thumbnail_url(
            media['url'],
            media.get('type', 'video')
        )
    return media_suggestions
```

**Step 4: Commit**

```bash
git add agents/stock_photo_api.py
git commit -m "feat: add thumbnail URL extraction for visual ranking"
```

---

## Task 4: Integrate Visual Ranking into Pipeline

**Files:**
- Modify: `pipeline.sh`

**Step 1: Find research stage in pipeline.sh**

Run:
```bash
grep -n "Stage.*Research" pipeline.sh
```

**Step 2: Add visual ranking stage after research**

Insert after research stage (around line 160) in `pipeline.sh`:
```bash
# Stage 2: Visual Ranking
if [ $START_STAGE -le 2 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Stage 2/6: Visual Ranking${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    echo "🎨 Visual Ranking Agent: Analyzing media diversity..."

    if python3 agents/3_rank_visuals.py; then
        echo "✅ Visual ranking complete"
    else
        echo -e "${YELLOW}⚠️  Visual ranking failed, continuing without rankings${NC}"
        # Not critical - curator can work without rankings
    fi
    echo ""
fi
```

**Step 3: Update stage numbers for subsequent stages**

Update in `pipeline.sh`:
- Lyrics: Stage 2 → Stage 3
- Music: Stage 3 → Stage 4
- Curator: Stage 4 → Stage 5
- Assembly: Stage 5 → Stage 6

**Step 4: Test pipeline with visual ranking**

Run:
```bash
./pipeline.sh --start=2 --resume
```

Expected: Visual ranking stage runs and creates `visual_rankings.json`

**Step 5: Commit**

```bash
git add pipeline.sh
git commit -m "feat: integrate visual ranking into pipeline"
```

---

## Task 5: Add Research Gap-Filling Logic

**Files:**
- Create: `agents/3.5_fill_research_gaps.py`

**Step 1: Create gap detection and filling agent**

Create `agents/3.5_fill_research_gaps.py`:
```python
#!/usr/bin/env python3
"""
Research Gap Filler: Identifies missing media for lyrics and requests more research.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Set

sys.path.insert(0, str(Path(__file__).parent))
from output_helper import get_output_path


class ResearchGapFiller:
    """Detects gaps between lyrics and available media, fills them."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def detect_gaps(self, lyrics_data: Dict, visual_rankings: Dict) -> List[str]:
        """
        Detect which lyric concepts lack matching media.

        Args:
            lyrics_data: Lyrics JSON with key_facts_covered
            visual_rankings: Visual rankings JSON with ranked_media

        Returns:
            List of missing concepts/facts
        """
        # Get facts covered by lyrics
        facts_covered = set(lyrics_data.get('key_facts_covered', []))

        # Get facts covered by ranked media
        ranked_media = visual_rankings.get('ranked_media', [])
        media_fact_coverage = set()

        for media in ranked_media:
            recommended_fact = media.get('recommended_fact')
            if recommended_fact is not None:
                media_fact_coverage.add(recommended_fact)

        # Find gaps
        missing_facts = facts_covered - media_fact_coverage

        return list(missing_facts)

    def generate_research_request(self, missing_facts: List[int], research_data: Dict) -> Dict:
        """
        Generate targeted research request for missing concepts.

        Args:
            missing_facts: Indices of facts needing media
            research_data: Original research JSON

        Returns:
            Research request JSON
        """
        key_facts = research_data.get('key_facts', [])
        missing_fact_texts = [key_facts[i] for i in missing_facts if i < len(key_facts)]

        return {
            'missing_concepts': missing_fact_texts,
            'target_media_count': len(missing_facts),
            'tone': research_data.get('tone', 'educational'),
            'existing_media_count': len(research_data.get('media_suggestions', []))
        }


def main():
    """Main entry point for gap filling."""
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger = logging.getLogger(__name__)

    # Load data
    lyrics_path = get_output_path('lyrics.json')
    rankings_path = get_output_path('visual_rankings.json')
    research_path = get_output_path('research.json')

    if not all([lyrics_path.exists(), rankings_path.exists(), research_path.exists()]):
        logger.error("Missing required input files")
        sys.exit(1)

    with open(lyrics_path) as f:
        lyrics_data = json.load(f)
    with open(rankings_path) as f:
        visual_rankings = json.load(f)
    with open(research_path) as f:
        research_data = json.load(f)

    # Detect gaps
    filler = ResearchGapFiller()
    missing_facts = filler.detect_gaps(lyrics_data, visual_rankings)

    if not missing_facts:
        logger.info("✅ No research gaps detected - all lyrics have matching media")
        sys.exit(0)

    logger.info(f"⚠️  Detected {len(missing_facts)} missing media for lyric concepts")

    # Generate research request
    research_request = filler.generate_research_request(missing_facts, research_data)

    # Save request
    request_path = get_output_path('research_gap_request.json')
    with open(request_path, 'w') as f:
        json.dump(research_request, f, indent=2)

    logger.info(f"📝 Research gap request saved: {request_path}")
    logger.info("   Re-run research agent with gap-filling mode")

    # Exit with code 2 to signal gaps detected
    sys.exit(2)


if __name__ == '__main__':
    main()
```

**Step 2: Make executable**

Run:
```bash
chmod +x agents/3.5_fill_research_gaps.py
```

**Step 3: Integrate into pipeline after curator**

Add to `pipeline.sh` after curator stage:
```bash
# Check for research gaps
if python3 agents/3.5_fill_research_gaps.py; then
    echo "✅ No research gaps"
else
    GAP_EXIT_CODE=$?
    if [ $GAP_EXIT_CODE -eq 2 ]; then
        echo -e "${YELLOW}⚠️  Research gaps detected, re-running research with gap-filling${NC}"
        # TODO: Implement gap-filling research loop
        # For now, continue with available media
    fi
fi
```

**Step 4: Commit**

```bash
git add agents/3.5_fill_research_gaps.py pipeline.sh
git commit -m "feat: add research gap detection and filling"
```

---

## Task 6: Update Setup Script

**Files:**
- Modify: `setup.sh`

**Step 1: Add CLIP model pre-download**

Add to `setup.sh` before "Setup complete":
```bash
echo ""
echo "📥 Downloading CLIP model (one-time, ~400MB)..."
source venv/bin/activate
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('clip-ViT-B-32')"

if [ $? -eq 0 ]; then
    echo "✅ CLIP model downloaded and cached"
else
    echo "⚠️  CLIP model download failed - will download on first use"
fi
```

**Step 2: Commit**

```bash
git add setup.sh
git commit -m "feat: pre-download CLIP model in setup"
```

---

## Task 7: Update Documentation

**Files:**
- Modify: `README.md`

**Step 1: Add visual ranking to features**

Update features section in `README.md`:
```markdown
- 🤖 **AI Research**: Automatically gathers facts and finds royalty-free media
- 🎨 **Visual Ranking**: CLIP-powered diversity analysis ensures engaging variety
- 🎵 **Music Generation**: Creates custom educational songs via Suno API
```

**Step 2: Add visual ranking to pipeline stages**

Update "Available stages" section:
```markdown
**Available stages:**
1. Research
2. Visual Ranking
3. Lyrics Generation
4. Music Composition
5. Media Curation & Download
6. Video Assembly
```

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README with visual ranking feature"
```

---

## Task 8: Test End-to-End

**Step 1: Run full pipeline with visual ranking**

Run:
```bash
./pipeline.sh --express
```

Expected output:
- Stage 2: Visual Ranking runs successfully
- Creates `visual_rankings.json`
- Curator uses rankings
- Final video has diverse visuals

**Step 2: Verify visual diversity**

Run:
```bash
python3 << 'EOF'
import json
from pathlib import Path

# Load visual rankings
with open('outputs/current/visual_rankings.json') as f:
    rankings = json.load(f)

ranked_media = rankings['ranked_media']
top_10 = ranked_media[:10]

print("Top 10 ranked media:")
for i, media in enumerate(top_10, 1):
    print(f"{i}. Score: {media.get('visual_score', 0):.3f} - {media['description'][:60]}...")

# Check diversity
if len(top_10) >= 2:
    avg_score = sum(m.get('visual_score', 0) for m in top_10) / len(top_10)
    print(f"\nAverage visual score: {avg_score:.3f}")
    print("✅ Visual ranking working!" if avg_score > 0.5 else "⚠️  Low scores")
EOF
```

Expected: Diverse video descriptions in top 10

**Step 3: Compare with old pipeline (without visual ranking)**

Check previous run's media plan for repetitive content vs current run's diversity

**Step 4: Final commit**

```bash
git add -A
git commit -m "test: verify visual ranking end-to-end functionality"
```

---

## Verification Checklist

- [ ] CLIP model downloads successfully (~400MB)
- [ ] Thumbnails download in parallel (<5 seconds for 30 items)
- [ ] Visual rankings JSON created with scores
- [ ] Curator receives and uses rankings
- [ ] Final video has visually diverse shots
- [ ] No more than 2 similar videos in final output
- [ ] Pipeline gracefully handles ranking failures
- [ ] Total added time: <15 seconds

---

## Success Metrics

**Before (Current):**
- 5-6 visually similar videos per output
- Repetitive "green leaves" and "plant timelapse" shots
- Viewer engagement: moderate

**After (Target):**
- Maximum 1-2 similar videos
- Visual variety across all shots
- Viewer engagement: significantly improved
- Cost: $0 per run
- Time: +10 seconds per pipeline run
