# Synchronized Video-Lyric System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Synchronize video switching to word-level lyric timestamps from Suno API and improve semantic matching between visuals and sung content.

**Architecture:** Enhance video assembly stage to fetch Suno timestamps, use AI for phrase grouping and key term extraction, apply CLIP + keyword boosting for semantic matching, and align video shots to phrase boundaries while keeping related concepts together.

**Tech Stack:** Python 3, Suno API, sentence-transformers (CLIP), moviepy, Anthropic Claude API (for AI analysis)

---

## Task 1: Create Suno API Integration Module

**Files:**
- Create: `agents/suno_lyrics_sync.py`
- Reference: `agents/output_helper.py` (for path utilities)

**Step 1: Write the failing test**

Create: `tests/test_suno_lyrics_sync.py`

```python
import pytest
from unittest.mock import Mock, patch
from agents.suno_lyrics_sync import SunoLyricsSync


def test_fetch_aligned_lyrics_success():
    """Test successful fetch of aligned lyrics."""
    sync = SunoLyricsSync(api_key="test_key")

    with patch('requests.post') as mock_post:
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {
                "code": 200,
                "data": {
                    "alignedWords": [
                        {"word": "Test", "startS": 0.5, "endS": 0.8, "success": True}
                    ]
                }
            }
        )

        result = sync.fetch_aligned_lyrics("task123", "audio456")

        assert "alignedWords" in result
        assert len(result["alignedWords"]) == 1
        assert result["alignedWords"][0]["word"] == "Test"


def test_fetch_aligned_lyrics_retry_on_failure():
    """Test retry logic on API failure."""
    sync = SunoLyricsSync(api_key="test_key", max_retries=2)

    with patch('requests.post') as mock_post:
        mock_post.side_effect = [
            Mock(status_code=500),
            Mock(status_code=200, json=lambda: {"code": 200, "data": {"alignedWords": []}})
        ]

        result = sync.fetch_aligned_lyrics("task123", "audio456")

        assert mock_post.call_count == 2
        assert "alignedWords" in result
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_suno_lyrics_sync.py -v`
Expected: FAIL with "No module named 'agents.suno_lyrics_sync'"

**Step 3: Write minimal implementation**

Create: `agents/suno_lyrics_sync.py`

```python
#!/usr/bin/env python3
"""
Suno API integration for fetching word-level lyric timestamps.
"""

import os
import time
import logging
from typing import Optional, Dict
import requests


class SunoLyricsSync:
    """Fetches word-level aligned lyrics from Suno API."""

    API_ENDPOINT = "https://api.sunoapi.org/api/v1/generate/get-timestamped-lyrics"

    def __init__(self, api_key: Optional[str] = None, max_retries: int = 3):
        """
        Initialize Suno API client.

        Args:
            api_key: Suno API key (defaults to SUNO_API_KEY env var)
            max_retries: Maximum number of retry attempts
        """
        self.api_key = api_key or os.getenv("SUNO_API_KEY")
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)

    def fetch_aligned_lyrics(self, task_id: str, audio_id: str) -> Dict:
        """
        Fetch word-level timestamps from Suno API.

        Args:
            task_id: Task ID from music generation
            audio_id: Audio ID from music generation

        Returns:
            Dictionary with alignedWords array

        Raises:
            Exception: If all retries fail
        """
        if not self.api_key:
            raise ValueError("SUNO_API_KEY not set")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "taskId": task_id,
            "audioId": audio_id
        }

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.API_ENDPOINT,
                    json=payload,
                    headers=headers,
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 200:
                        return data.get("data", {})
                    else:
                        self.logger.warning(f"API returned error: {data.get('msg')}")
                else:
                    self.logger.warning(f"HTTP {response.status_code}: {response.text}")

            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}")

            if attempt < self.max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                time.sleep(wait_time)

        raise Exception(f"Failed to fetch aligned lyrics after {self.max_retries} attempts")
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_suno_lyrics_sync.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add tests/test_suno_lyrics_sync.py agents/suno_lyrics_sync.py
git commit -m "feat: add Suno API integration for aligned lyrics

- Fetch word-level timestamps with retry logic
- Exponential backoff on failures
- Unit tests with mocked API responses"
```

---

## Task 2: Create Phrase Grouping Module

**Files:**
- Create: `agents/phrase_grouper.py`
- Reference: `agents/output_helper.py`

**Step 1: Write the failing test**

Create: `tests/test_phrase_grouper.py`

```python
import pytest
from agents.phrase_grouper import PhraseGrouper


def test_parse_aligned_words_into_phrases():
    """Test parsing aligned words into phrase boundaries."""
    grouper = PhraseGrouper()

    aligned_words = [
        {"word": "Look", "startS": 0.5, "endS": 0.8},
        {"word": "at", "startS": 0.8, "endS": 0.9},
        {"word": "a", "startS": 0.9, "endS": 1.0},
        {"word": "leaf", "startS": 1.0, "endS": 1.3},
        # Gap > 0.3s indicates phrase boundary
        {"word": "It's", "startS": 1.8, "endS": 2.0},
        {"word": "green", "startS": 2.0, "endS": 2.3},
    ]

    phrases = grouper.parse_into_phrases(aligned_words, gap_threshold=0.3)

    assert len(phrases) == 2
    assert phrases[0]["text"] == "Look at a leaf"
    assert phrases[0]["startS"] == 0.5
    assert phrases[0]["endS"] == 1.3
    assert phrases[1]["text"] == "It's green"


def test_extract_key_terms_with_ai():
    """Test AI-based key term extraction."""
    grouper = PhraseGrouper()

    lyrics = "Chloroplasts are the power plants inside"
    key_facts = ["Chloroplasts contain chlorophyll"]

    # Mock the AI call
    with pytest.mock_module('anthropic') as mock_anthropic:
        mock_client = mock_anthropic.Anthropic.return_value
        mock_client.messages.create.return_value.content = [
            type('obj', (), {'text': '["chloroplasts", "power plants"]'})
        ]

        terms = grouper.extract_key_terms(lyrics, key_facts)

        assert "chloroplasts" in terms
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_phrase_grouper.py -v`
Expected: FAIL with "No module named 'agents.phrase_grouper'"

**Step 3: Write minimal implementation**

Create: `agents/phrase_grouper.py`

```python
#!/usr/bin/env python3
"""
AI-powered phrase grouping and key term extraction.
"""

import os
import json
import logging
from typing import List, Dict
from anthropic import Anthropic


class PhraseGrouper:
    """Groups lyric phrases by semantic topic using AI."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize phrase grouper.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.client = Anthropic(api_key=api_key)
        self.logger = logging.getLogger(__name__)

    def parse_into_phrases(self, aligned_words: List[Dict], gap_threshold: float = 0.3) -> List[Dict]:
        """
        Parse aligned words into phrase boundaries based on timing gaps.

        Args:
            aligned_words: List of word dictionaries with startS, endS, word
            gap_threshold: Minimum gap (seconds) to split phrases

        Returns:
            List of phrase dictionaries with text, startS, endS
        """
        if not aligned_words:
            return []

        phrases = []
        current_phrase = []

        for i, word in enumerate(aligned_words):
            current_phrase.append(word)

            # Check if next word has significant gap
            if i < len(aligned_words) - 1:
                next_word = aligned_words[i + 1]
                gap = next_word["startS"] - word["endS"]

                if gap > gap_threshold:
                    # End current phrase
                    phrases.append(self._build_phrase(current_phrase))
                    current_phrase = []
            else:
                # Last word - end phrase
                phrases.append(self._build_phrase(current_phrase))

        return phrases

    def _build_phrase(self, words: List[Dict]) -> Dict:
        """Build phrase dict from word list."""
        text = " ".join(w["word"] for w in words)
        return {
            "text": text,
            "startS": words[0]["startS"],
            "endS": words[-1]["endS"]
        }

    def extract_key_terms(self, lyrics: str, key_facts: List[str]) -> List[str]:
        """
        Extract key scientific terms from lyrics using AI.

        Args:
            lyrics: Full lyrics text
            key_facts: Key facts from research

        Returns:
            List of key scientific terms
        """
        prompt = f"""Extract key scientific terms from these educational lyrics.

Lyrics:
{lyrics}

Key Facts from Research:
{json.dumps(key_facts, indent=2)}

Identify:
- Enzyme names (e.g., RuBisCO, ATP synthase)
- Molecule names (e.g., chlorophyll, glucose, oxygen)
- Processes (e.g., photosynthesis, electron transport)
- Organelles (e.g., chloroplasts, mitochondria)
- Other key scientific concepts

Return ONLY a JSON array of terms, lowercase, no duplicates.
Example: ["chlorophyll", "atp synthase", "electron transport", "photosynthesis"]"""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.content[0].text.strip()
            # Extract JSON array from response
            if "[" in result_text and "]" in result_text:
                json_start = result_text.index("[")
                json_end = result_text.rindex("]") + 1
                terms = json.loads(result_text[json_start:json_end])
                return terms

            self.logger.warning("Could not parse AI response")
            return []

        except Exception as e:
            self.logger.error(f"Key term extraction failed: {e}")
            return []

    def group_phrases_by_topic(self, phrases: List[Dict], key_terms: List[str]) -> List[Dict]:
        """
        Group consecutive phrases by semantic topic using AI.

        Args:
            phrases: List of phrase dicts with text, startS, endS
            key_terms: List of key scientific terms

        Returns:
            List of phrase groups with topic, phrases, key_terms, timing
        """
        if not phrases:
            return []

        # Prepare phrases for AI
        phrases_text = "\n".join([f"{i+1}. {p['text']}" for i, p in enumerate(phrases)])

        prompt = f"""Group these lyric phrases by the scientific concept they discuss.

Phrases:
{phrases_text}

Key Scientific Terms:
{json.dumps(key_terms, indent=2)}

Rules:
- Keep groups as large as possible while maintaining topic coherence
- Consecutive phrases about the same concept should be grouped together
- Each group should have a clear scientific topic
- Identify which key terms appear in each group

Return JSON array of groups:
[
  {{
    "phrase_indices": [0, 1],
    "topic": "chlorophyll and light absorption",
    "key_terms": ["chlorophyll", "leaf"]
  }},
  ...
]"""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.content[0].text.strip()
            # Extract JSON array
            if "[" in result_text and "]" in result_text:
                json_start = result_text.index("[")
                json_end = result_text.rindex("]") + 1
                groups_data = json.loads(result_text[json_start:json_end])

                # Build full group objects
                groups = []
                for g in groups_data:
                    group_phrases = [phrases[i] for i in g["phrase_indices"]]
                    groups.append({
                        "group_id": len(groups) + 1,
                        "topic": g["topic"],
                        "phrases": group_phrases,
                        "key_terms": g.get("key_terms", []),
                        "start_time": group_phrases[0]["startS"],
                        "end_time": group_phrases[-1]["endS"],
                        "duration": group_phrases[-1]["endS"] - group_phrases[0]["startS"]
                    })

                return groups

        except Exception as e:
            self.logger.error(f"Phrase grouping failed: {e}")
            # Fallback: each phrase is its own group
            return [
                {
                    "group_id": i + 1,
                    "topic": phrase["text"][:30],
                    "phrases": [phrase],
                    "key_terms": [],
                    "start_time": phrase["startS"],
                    "end_time": phrase["endS"],
                    "duration": phrase["endS"] - phrase["startS"]
                }
                for i, phrase in enumerate(phrases)
            ]
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_phrase_grouper.py::test_parse_aligned_words_into_phrases -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_phrase_grouper.py agents/phrase_grouper.py
git commit -m "feat: add AI-powered phrase grouping

- Parse aligned words into phrase boundaries
- Extract key scientific terms with AI
- Group phrases by semantic topic
- Fallback to individual phrases on failure"
```

---

## Task 3: Create Semantic Matching Module

**Files:**
- Create: `agents/semantic_matcher.py`
- Reference: `agents/3_rank_visuals.py` (for CLIP usage)

**Step 1: Write the failing test**

Create: `tests/test_semantic_matcher.py`

```python
import pytest
import numpy as np
from agents.semantic_matcher import SemanticMatcher


def test_match_videos_to_groups():
    """Test CLIP + keyword boosting matching."""
    matcher = SemanticMatcher()

    phrase_groups = [
        {
            "group_id": 1,
            "topic": "ATP synthase molecular motor",
            "key_terms": ["atp synthase", "molecular motor"],
            "duration": 5.0
        }
    ]

    available_media = [
        {
            "url": "video1.mp4",
            "description": "ATP synthase rotating and producing energy"
        },
        {
            "url": "video2.mp4",
            "description": "plant cell structure"
        }
    ]

    matched = matcher.match_videos_to_groups(phrase_groups, available_media)

    assert len(matched) == 1
    assert matched[0]["video_url"] == "video1.mp4"
    assert matched[0]["match_score"] > 0.5
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_semantic_matcher.py -v`
Expected: FAIL with "No module named 'agents.semantic_matcher'"

**Step 3: Write minimal implementation**

Create: `agents/semantic_matcher.py`

```python
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
        video_texts = [v["description"] for v in available_media]
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

                # Apply keyword boosting
                video_desc_lower = video["description"].lower()
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
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_semantic_matcher.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_semantic_matcher.py agents/semantic_matcher.py
git commit -m "feat: add semantic video-to-phrase matching

- CLIP embeddings for semantic similarity
- Keyword boosting (2x multiplier)
- Diversity penalty for recently used videos
- Topic continuation detection for smooth transitions"
```

---

## Task 4: Enhance Video Assembly with Synchronization

**Files:**
- Modify: `agents/5_assemble_video.py`
- Reference: `agents/suno_lyrics_sync.py`, `agents/phrase_grouper.py`, `agents/semantic_matcher.py`

**Step 1: Add configuration loading**

Modify: `agents/5_assemble_video.py`

Add after imports (around line 32):

```python
def load_sync_config():
    """Load lyric sync configuration."""
    config_path = Path("config/config.json")
    with open(config_path) as f:
        config = json.load(f)
    return config.get("lyric_sync", {
        "enabled": True,
        "min_phrase_duration": 1.5,
        "phrase_gap_threshold": 0.3,
        "keyword_boost_multiplier": 2.0,
        "transition_duration": 0.3
    })
```

**Step 2: Add synchronized assembly function**

Add before `assemble_video()` function:

```python
def fetch_and_process_lyrics(music_metadata: dict, research_data: dict, sync_config: dict):
    """
    Fetch timestamps and create phrase groups.

    Args:
        music_metadata: Music metadata with task_id and audio_id
        research_data: Research data with key_facts
        sync_config: Sync configuration

    Returns:
        Tuple of (aligned_lyrics, phrase_groups) or (None, None) on failure
    """
    from suno_lyrics_sync import SunoLyricsSync
    from phrase_grouper import PhraseGrouper

    logger = logging.getLogger(__name__)

    # Fetch timestamps
    try:
        sync = SunoLyricsSync()
        task_id = music_metadata.get("task_id")
        audio_id = music_metadata.get("audio_id")

        if not task_id or not audio_id:
            logger.warning("Missing task_id or audio_id, cannot fetch timestamps")
            return None, None

        logger.info(f"Fetching aligned lyrics for audio {audio_id}...")
        aligned_data = sync.fetch_aligned_lyrics(task_id, audio_id)

        # Save aligned lyrics
        aligned_path = get_output_path("lyrics_aligned.json")
        with open(aligned_path, 'w') as f:
            json.dump(aligned_data, f, indent=2)
        logger.info(f"Saved aligned lyrics to {aligned_path}")

    except Exception as e:
        logger.error(f"Failed to fetch aligned lyrics: {e}")
        return None, None

    # Parse and group phrases
    try:
        grouper = PhraseGrouper()

        # Parse into phrases
        aligned_words = aligned_data.get("alignedWords", [])
        phrases = grouper.parse_into_phrases(
            aligned_words,
            gap_threshold=sync_config["phrase_gap_threshold"]
        )

        # Extract key terms
        lyrics_text = " ".join([w["word"] for w in aligned_words])
        key_facts = research_data.get("key_facts", [])
        key_terms = grouper.extract_key_terms(lyrics_text, key_facts)

        # Group by topic
        phrase_groups = grouper.group_phrases_by_topic(phrases, key_terms)

        # Save phrase groups
        groups_path = get_output_path("phrase_groups.json")
        with open(groups_path, 'w') as f:
            json.dump(phrase_groups, f, indent=2)
        logger.info(f"Saved {len(phrase_groups)} phrase groups to {groups_path}")

        return aligned_data, phrase_groups

    except Exception as e:
        logger.error(f"Failed to process phrases: {e}")
        return None, None


def create_synchronized_plan(phrase_groups: List[Dict], approved_media: List[Dict], sync_config: dict) -> Dict:
    """
    Create synchronized media plan using semantic matching.

    Args:
        phrase_groups: Phrase groups from AI
        approved_media: Available media from curator
        sync_config: Sync configuration

    Returns:
        Synchronized plan dict
    """
    from semantic_matcher import SemanticMatcher

    logger = logging.getLogger(__name__)

    # Match videos to phrase groups
    matcher = SemanticMatcher(keyword_boost=sync_config["keyword_boost_multiplier"])
    matched_groups = matcher.match_videos_to_groups(phrase_groups, approved_media)

    # Build shot list
    shots = []
    for group in matched_groups:
        # Find media object
        media = next((m for m in approved_media if m.get("url") == group["video_url"] or m.get("media_url") == group["video_url"]), None)

        if not media or "local_path" not in media:
            logger.warning(f"No local media found for {group['video_url']}, skipping")
            continue

        shot = {
            "shot_number": len(shots) + 1,
            "local_path": media["local_path"],
            "media_type": media.get("media_type", "video"),
            "description": group["video_description"],
            "start_time": group["start_time"],
            "end_time": group["end_time"],
            "duration": max(group["duration"], sync_config["min_phrase_duration"]),
            "lyrics_match": " / ".join([p["text"] for p in group["phrases"]]),
            "topic": group["topic"],
            "key_terms": group["key_terms"],
            "match_score": group["match_score"],
            "transition": "crossfade"
        }
        shots.append(shot)

    # Set first and last transitions to fade
    if shots:
        shots[0]["transition"] = "fade"
        shots[-1]["transition"] = "fade"

    total_duration = shots[-1]["end_time"] if shots else 0

    plan = {
        "shot_list": shots,
        "total_duration": total_duration,
        "total_shots": len(shots),
        "transition_style": "smooth",
        "pacing": "synchronized",
        "sync_method": "suno_timestamps"
    }

    # Save synchronized plan
    sync_path = get_output_path("synchronized_plan.json")
    with open(sync_path, 'w') as f:
        json.dump(plan, f, indent=2)
    logger.info(f"Saved synchronized plan to {sync_path}")

    return plan
```

**Step 3: Modify main() to use synchronization**

Replace `main()` function:

```python
def main():
    """Main execution."""
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger = logging.getLogger(__name__)

    print("🎞️  Video Assembly Agent: Creating final video...")

    # Load configuration
    video_settings = load_config()
    sync_config = load_sync_config()

    # Load approved media
    approved_data = load_approved_media()

    # Check for audio
    audio_path = get_output_path("song.mp3")
    if not audio_path.exists():
        print(f"❌ Error: {audio_path} not found")
        print("Run composer agent first: ./agents/3_compose.py")
        sys.exit(1)

    # Attempt synchronized assembly if enabled
    if sync_config.get("enabled", True):
        try:
            # Load music metadata
            metadata_path = get_output_path("music_metadata.json")
            if metadata_path.exists():
                with open(metadata_path) as f:
                    music_metadata = json.load(f)

                # Load research data
                research_path = get_output_path("research.json")
                if research_path.exists():
                    with open(research_path) as f:
                        research_data = json.load(f)

                    print("\n🎵 Fetching lyric timestamps from Suno API...")
                    aligned_data, phrase_groups = fetch_and_process_lyrics(
                        music_metadata, research_data, sync_config
                    )

                    if phrase_groups:
                        print(f"✅ Created {len(phrase_groups)} semantic phrase groups")
                        print("\n🎯 Matching videos to phrase groups...")

                        # Get available media from approved list
                        available_media = [
                            {
                                "url": shot.get("media_url", ""),
                                "description": shot.get("description", ""),
                                "local_path": shot.get("local_path"),
                                "media_type": shot.get("media_type", "video")
                            }
                            for shot in approved_data["shot_list"]
                            if "local_path" in shot
                        ]

                        synchronized_plan = create_synchronized_plan(
                            phrase_groups, available_media, sync_config
                        )

                        print(f"✅ Matched {len(synchronized_plan['shot_list'])} synchronized shots")
                        print("\n🎬 Assembling synchronized video...")

                        # Use synchronized plan instead of approved_data
                        output_path = assemble_video(synchronized_plan, video_settings, str(audio_path))

                        print(f"\n✅ Synchronized video assembly complete!")
                        print(f"📹 Final video: {output_path}")
                        print(f"🎯 Synchronization: {len(phrase_groups)} phrase-aligned shots")
                        print(f"\nNext steps:")
                        print(f"  - Preview: open {output_path}")
                        print(f"  - Compare with phrase_groups.json to verify timing")
                        return

        except Exception as e:
            logger.warning(f"Synchronized assembly failed: {e}")
            logger.warning("Falling back to curator's media plan")

    # Fallback to original assembly
    print("\n🎬 Assembling video with curator's timing...")
    output_path = assemble_video(approved_data, video_settings, str(audio_path))

    print(f"\n✅ Video assembly complete!")
    print(f"📹 Final video: {output_path}")
    print(f"\nNext steps:")
    print(f"  - Preview: open {output_path}")
    print(f"  - Edit in iMovie if needed")
    print(f"  - Share to TikTok/Instagram Reels")
```

**Step 4: Test with existing run data**

Run: `OUTPUT_DIR=outputs/runs/20251117_185735 python3 agents/5_assemble_video.py`

Expected: Should attempt synchronization, may fall back if SUNO_API_KEY not set

**Step 5: Commit**

```bash
git add agents/5_assemble_video.py
git commit -m "feat: integrate synchronized video assembly

- Fetch Suno timestamps in assembly stage
- AI phrase grouping and key term extraction
- Semantic video-to-phrase matching
- Fallback to curator timing on failure
- Save intermediate files for debugging"
```

---

## Task 5: Add Configuration File

**Files:**
- Modify: `config/config.json`

**Step 1: Add lyric_sync configuration**

Add to `config/config.json` after `video_settings`:

```json
  "lyric_sync": {
    "enabled": true,
    "min_phrase_duration": 1.5,
    "max_phrase_duration": 10.0,
    "phrase_gap_threshold": 0.3,
    "keyword_boost_multiplier": 2.0,
    "diversity_penalty": 0.1,
    "transition_duration": 0.3
  }
```

**Step 2: Commit**

```bash
git add config/config.json
git commit -m "config: add lyric synchronization settings

- Enable/disable sync feature
- Phrase duration constraints
- Semantic matching parameters
- Transition timing"
```

---

## Task 6: Update Setup and Documentation

**Files:**
- Modify: `setup.sh`
- Modify: `README.md`

**Step 1: Add SUNO_API_KEY to setup instructions**

Modify `setup.sh` to add after Giphy API key check:

```bash
# Check for Suno API key (optional, for lyric sync)
if [ -z "$SUNO_API_KEY" ]; then
    echo ""
    echo "⚠️  SUNO_API_KEY not set"
    echo "Lyric synchronization will be disabled."
    echo ""
    echo "To enable synchronized video-lyric switching:"
    echo "1. Get API key from https://sunoapi.org"
    echo "2. Add to your shell profile:"
    echo "   export SUNO_API_KEY='your_key_here'"
    echo ""
else
    echo "✅ Suno API key configured"
fi
```

**Step 2: Update README with synchronized feature**

Add to README.md features section:

```markdown
### 🎵 Synchronized Video-Lyric Switching

**Word-Level Precision**: Videos switch exactly when key scientific terms are sung, using Suno API's word-level timestamps.

**AI Semantic Grouping**: Phrases discussing the same concept stay on the same video, creating smooth educational flow.

**CLIP + Keyword Boosting**: Videos are matched to phrases using semantic similarity plus 2x boost for exact keyword matches (e.g., "ATP synthase" lyric → ATP synthase animation).

**Graceful Fallback**: If Suno API is unavailable, falls back to curator's timing automatically.

**Configuration**: Control sync behavior in `config/config.json`:
- `phrase_gap_threshold`: Minimum pause to split phrases (default: 0.3s)
- `min_phrase_duration`: Minimum shot duration (default: 1.5s)
- `keyword_boost_multiplier`: Boost for keyword matches (default: 2.0)
```

Add to setup section:

```markdown
### Optional: Lyric Synchronization

For synchronized video-lyric switching:

```bash
export SUNO_API_KEY='your_suno_api_key'
```

Get your key from [SunoAPI.org](https://sunoapi.org)

Without this key, the system falls back to curator's timing.
```

**Step 3: Commit**

```bash
git add setup.sh README.md
git commit -m "docs: add lyric synchronization setup and features

- Setup instructions for SUNO_API_KEY
- Feature documentation for synchronized switching
- Configuration reference
- Fallback behavior explanation"
```

---

## Task 7: End-to-End Testing

**Files:**
- Create: `tests/test_integration_sync.py`

**Step 1: Create integration test**

```python
import pytest
import json
from pathlib import Path


def test_synchronized_assembly_integration():
    """Test full synchronized assembly workflow."""
    # This requires actual API keys and run data
    # Skip if not available
    import os
    if not os.getenv("SUNO_API_KEY"):
        pytest.skip("SUNO_API_KEY not set")

    # Use existing run data
    run_dir = Path("outputs/runs/20251117_185735")
    if not run_dir.exists():
        pytest.skip("Test run data not available")

    # Set output dir
    os.environ["OUTPUT_DIR"] = str(run_dir)

    # Run assembly
    from agents.assemble_video import main
    main()

    # Check outputs
    assert (run_dir / "lyrics_aligned.json").exists()
    assert (run_dir / "phrase_groups.json").exists()
    assert (run_dir / "synchronized_plan.json").exists()
    assert (run_dir / "final_video.mp4").exists()

    # Validate synchronized plan
    with open(run_dir / "synchronized_plan.json") as f:
        plan = json.load(f)

    assert plan["sync_method"] == "suno_timestamps"
    assert len(plan["shot_list"]) > 0
    assert all("start_time" in shot for shot in plan["shot_list"])
```

**Step 2: Run integration test**

Run: `python3 -m pytest tests/test_integration_sync.py -v -s`

Expected: SKIP if SUNO_API_KEY not set, or PASS if available

**Step 3: Manual validation**

1. Run pipeline: `./pipeline.sh`
2. Check phrase groups: `cat outputs/current/phrase_groups.json | jq '.[] | {topic, key_terms, duration}'`
3. Check synchronized plan: `cat outputs/current/synchronized_plan.json | jq '.shot_list[] | {shot_number, topic, duration, match_score}'`
4. Watch video: `open outputs/current/final_video.mp4`
5. Verify: Key terms (chlorophyll, ATP synthase, etc.) appear when matching videos show

**Step 4: Commit**

```bash
git add tests/test_integration_sync.py
git commit -m "test: add synchronized assembly integration test

- Full workflow test with real API
- Skip if SUNO_API_KEY not available
- Validate output file structure
- Manual validation checklist"
```

---

## Implementation Complete

All tasks completed. The synchronized video-lyric system is now integrated into the pipeline.

**Key Files Created:**
- `agents/suno_lyrics_sync.py` - Suno API integration
- `agents/phrase_grouper.py` - AI phrase grouping
- `agents/semantic_matcher.py` - CLIP + keyword matching
- Enhanced `agents/5_assemble_video.py` - Synchronized assembly

**Testing:**
- Unit tests for each module
- Integration test for full workflow
- Manual validation checklist

**Next Steps:**
1. Set SUNO_API_KEY environment variable
2. Run full pipeline to test synchronization
3. Review phrase_groups.json to validate AI grouping
4. Watch final video to verify timing accuracy
5. Tune configuration if needed (keyword_boost, phrase_gap_threshold)
