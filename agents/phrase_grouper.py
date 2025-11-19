#!/usr/bin/env python3
"""
AI-powered phrase grouping and key term extraction.
"""

import os
import json
import logging
from typing import List, Dict, Optional
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
