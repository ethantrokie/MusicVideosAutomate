#!/usr/bin/env python3
"""
AI-powered phrase grouping and key term extraction.
"""

import os
import json
import logging
import subprocess
from typing import List, Dict, Optional


class PhraseGrouper:
    """Groups lyric phrases by semantic topic using AI."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize phrase grouper.

        Args:
            api_key: Unused (kept for compatibility)
        """
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

        # Primary: Gap-based detection
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

        # Defensive Fallback #1: Punctuation-based splitting if < 3 phrase groups
        if len(phrases) < 3:
            self.logger.warning(f"Gap-based detection produced only {len(phrases)} phrase groups. Trying punctuation-based splitting...")
            phrases = self._split_by_punctuation(aligned_words)

        # Defensive Fallback #2: Structural marker splitting if still < 3 groups
        if len(phrases) < 3:
            self.logger.warning(f"Punctuation-based detection produced only {len(phrases)} phrase groups. Trying structural marker splitting...")
            phrases = self._split_by_structural_markers(aligned_words)

        # Log which method was used
        if len(phrases) >= 3:
            self.logger.info(f"Successfully created {len(phrases)} phrase groups")
        else:
            self.logger.warning(f"All fallback methods exhausted. Created {len(phrases)} phrase groups")

        return phrases

    def _build_phrase(self, words: List[Dict]) -> Dict:
        """Build phrase dict from word list."""
        text = " ".join(w["word"] for w in words)
        return {
            "text": text,
            "startS": words[0]["startS"],
            "endS": words[-1]["endS"]
        }

    def _split_by_punctuation(self, aligned_words: List[Dict]) -> List[Dict]:
        """Split phrases based on punctuation marks."""
        if not aligned_words:
            return []

        phrases = []
        current_phrase = []

        for i, word in enumerate(aligned_words):
            current_phrase.append(word)

            # Check if word ends with sentence-ending punctuation
            word_text = word["word"].rstrip()
            if word_text.endswith(('.', '!', '?', ',')) or i == len(aligned_words) - 1:
                if current_phrase:
                    phrases.append(self._build_phrase(current_phrase))
                    current_phrase = []

        # Handle remaining words if any
        if current_phrase:
            phrases.append(self._build_phrase(current_phrase))

        return phrases

    def _split_by_structural_markers(self, aligned_words: List[Dict]) -> List[Dict]:
        """Split phrases based on structural markers like [Verse], [Chorus], [Bridge]."""
        if not aligned_words:
            return []

        phrases = []
        current_phrase = []

        structural_markers = ['[Verse', '[Chorus', '[Bridge', '[Pre-Chorus', '[Outro', '[Intro']

        for i, word in enumerate(aligned_words):
            word_text = word["word"].strip()

            # Check if this word starts a new structural section
            is_marker = any(word_text.startswith(marker) for marker in structural_markers)

            if is_marker and current_phrase:
                # Save current phrase before starting new section
                phrases.append(self._build_phrase(current_phrase))
                current_phrase = [word]
            else:
                current_phrase.append(word)

            # End phrase at last word
            if i == len(aligned_words) - 1 and current_phrase:
                phrases.append(self._build_phrase(current_phrase))

        return phrases

    def _split_long_groups(self, phrases: List[Dict], max_duration: float = 4.0) -> List[Dict]:
        """
        Split phrase groups that are longer than max_duration seconds.
        Splits at punctuation boundaries or evenly if no punctuation.

        Args:
            phrases: List of phrase dicts with text, startS, endS
            max_duration: Maximum duration in seconds

        Returns:
            List of phrase dicts with long groups split
        """
        result = []

        for phrase in phrases:
            duration = phrase["endS"] - phrase["startS"]

            if duration <= max_duration:
                # Group is acceptable, keep as-is
                result.append(phrase)
            else:
                # Group is too long, need to split
                self.logger.debug(f"Splitting {duration:.1f}s group: {phrase['text'][:50]}...")

                # Split text on sentence/clause boundaries
                text = phrase["text"]
                words = text.split()

                # Estimate time per word
                time_per_word = duration / len(words) if words else 0

                # Calculate how many words per target chunk (aim for 3s chunks)
                target_chunk_duration = 3.0
                words_per_chunk = int(target_chunk_duration / time_per_word) if time_per_word > 0 else len(words)
                words_per_chunk = max(1, min(words_per_chunk, len(words)))

                # Split words into chunks
                chunks = []
                current_chunk = []
                for i, word in enumerate(words):
                    current_chunk.append(word)

                    # Split on punctuation or chunk size
                    has_punctuation = any(word.rstrip().endswith(p) for p in [',', '.', '!', '?', ';'])
                    is_chunk_full = len(current_chunk) >= words_per_chunk
                    is_last_word = i == len(words) - 1

                    if (has_punctuation and is_chunk_full) or is_last_word:
                        chunks.append(current_chunk)
                        current_chunk = []
                    elif not has_punctuation and len(current_chunk) >= words_per_chunk * 1.5:
                        # Force split if chunk is getting too large
                        chunks.append(current_chunk)
                        current_chunk = []

                # Handle remaining words
                if current_chunk:
                    if chunks:
                        # Add to last chunk
                        chunks[-1].extend(current_chunk)
                    else:
                        chunks.append(current_chunk)

                # Create phrase objects for each chunk
                current_time = phrase["startS"]
                for chunk_words in chunks:
                    chunk_duration = len(chunk_words) * time_per_word
                    chunk_text = " ".join(chunk_words)

                    result.append({
                        "text": chunk_text,
                        "startS": current_time,
                        "endS": min(current_time + chunk_duration, phrase["endS"])
                    })
                    current_time += chunk_duration

        return result

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
            # Call Claude Code CLI
            result = subprocess.run(
                ["claude", "-p", prompt, "--model", "claude-haiku-4-5", "--dangerously-skip-permissions"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                self.logger.error(f"Claude CLI failed: {result.stderr}")
                return []

            result_text = result.stdout.strip()
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
            # Call Claude Code CLI
            result = subprocess.run(
                ["claude", "-p", prompt, "--model", "claude-haiku-4-5", "--dangerously-skip-permissions"],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                self.logger.error(f"Claude CLI failed: {result.stderr}")
                raise Exception("Claude CLI failed")

            result_text = result.stdout.strip()
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

    def merge_related_phrases(self, phrases: List[Dict], key_terms: List[str]) -> List[Dict]:
        """
        Merge consecutive phrases that share key scientific terms.
        Keeps simple {text, startS, endS} structure for curator compatibility.

        Args:
            phrases: List of phrase dicts with text, startS, endS
            key_terms: List of key scientific terms

        Returns:
            List of merged phrase dicts (same structure)
        """
        if not phrases or len(phrases) < 2:
            return phrases

        # Prepare phrases for AI analysis
        phrases_text = "\n".join([f"{i}. {p['text']}" for i, p in enumerate(phrases)])

        prompt = f"""Analyze these lyric phrases and identify which CONSECUTIVE phrases should be merged to keep related concepts together.

Phrases:
{phrases_text}

Key Scientific Terms:
{json.dumps(key_terms, indent=2)}

Rules:
- Only merge CONSECUTIVE phrases (e.g., phrase 2 and 3, not 1 and 5)
- BE EXTREMELY CONSERVATIVE with merging - only merge when phrases are VERY closely related
- Merge phrases that discuss the EXACT SAME specific concept or step in a process
- Example: "The chlorophyll absorbs light" + "it captures photons from the sun" → should merge (same specific concept)
- Example: "The chlorophyll absorbs light" + "Then electrons move through the chain" → don't merge (different steps)
- Keep structural markers ([Verse], [Chorus], [Bridge]) separate from content
- TARGET: 2-4 seconds per phrase group - NEVER create groups longer than 6 seconds
- If a phrase discusses multiple distinct concepts, keep it separate
- DEFAULT to keeping phrases separate unless they're discussing the EXACT same thing
- Better to have MORE small groups (2-4s each) than fewer large groups

Return a JSON array of merge groups. Each group is an array of phrase indices to merge:
[
  [0, 1],      // Merge phrase 0 and 1 (very closely related)
  [2],         // Keep phrase 2 alone
  [3, 4],      // Merge phrases 3 and 4 (same specific concept)
  [5],         // Keep phrase 5 alone
  ...
]

IMPORTANT:
- Every phrase index from 0 to {len(phrases)-1} must appear exactly once
- Favor keeping phrases separate unless they're discussing the EXACT same thing
- Better to have MORE groups with good semantic coherence than fewer large groups"""

        try:
            # Call Claude Code CLI with lightweight model
            result = subprocess.run(
                ["claude", "-p", prompt, "--model", "claude-haiku-4-5", "--dangerously-skip-permissions"],
                capture_output=True,
                text=True,
                timeout=45
            )

            if result.returncode != 0:
                self.logger.warning(f"Claude CLI failed for phrase merging: {result.stderr}")
                return phrases

            result_text = result.stdout.strip()

            # Debug: Log the actual AI response
            self.logger.debug(f"AI Response: {result_text}")

            # Extract JSON array - find the first complete JSON array
            if "[" in result_text and "]" in result_text:
                json_start = result_text.index("[")
                # Find matching closing bracket by counting brackets
                bracket_count = 0
                json_end = json_start
                for i, char in enumerate(result_text[json_start:], start=json_start):
                    if char == "[":
                        bracket_count += 1
                    elif char == "]":
                        bracket_count -= 1
                        if bracket_count == 0:
                            json_end = i + 1
                            break

                json_str = result_text[json_start:json_end]
                self.logger.debug(f"Extracted JSON: {json_str}")

                try:
                    merge_groups = json.loads(json_str)
                except json.JSONDecodeError as e:
                    self.logger.warning(f"JSON parsing failed: {e}, trying to clean response")
                    # Try to extract just the array portion more carefully
                    import re
                    # Look for a valid JSON array pattern
                    match = re.search(r'\[\s*\[.*?\]\s*\]', result_text, re.DOTALL)
                    if match:
                        merge_groups = json.loads(match.group(0))
                    else:
                        self.logger.warning("Could not extract valid JSON array")
                        return phrases

                # Build merged phrases
                merged_phrases = []
                for group in merge_groups:
                    if isinstance(group, list):
                        if len(group) == 1:
                            # Single phrase, keep as-is
                            merged_phrases.append(phrases[group[0]])
                        else:
                            # Merge multiple phrases
                            group_phrases = [phrases[i] for i in group]
                            merged_text = " ".join(p["text"] for p in group_phrases)
                            merged_phrases.append({
                                "text": merged_text,
                                "startS": group_phrases[0]["startS"],
                                "endS": group_phrases[-1]["endS"]
                            })
                    else:
                        # Single index (not in array)
                        merged_phrases.append(phrases[group])

                self.logger.info(f"Merged {len(phrases)} phrases into {len(merged_phrases)} semantic groups")

                # POST-PROCESSING: Split any groups longer than 4 seconds
                final_phrases = self._split_long_groups(merged_phrases, max_duration=4.0)
                if len(final_phrases) != len(merged_phrases):
                    self.logger.info(f"Split {len(merged_phrases) - len(final_phrases)} overly long groups, now have {len(final_phrases)} groups")

                return final_phrases

            self.logger.warning("Could not parse merge groups, returning original phrases")
            return phrases

        except Exception as e:
            self.logger.warning(f"Phrase merging failed: {e}, returning original phrases")
            return phrases
