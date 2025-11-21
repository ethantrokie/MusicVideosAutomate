#!/Users/ethantrokie/SoftwareDevProjects/MusicVideosAutomate/venv/bin/python3
"""
Change guardian - validates proposed config changes against guardrails.
Prevents unsafe or out-of-bounds modifications.
"""

import json
import re
from pathlib import Path
from typing import Dict, Tuple


class ChangeGuardian:
    """Validates proposed configuration changes."""

    def __init__(self, guardrails_path: str = "automation/config/guardrails.json"):
        with open(guardrails_path) as f:
            self.guardrails = json.load(f)

    def validate_change(self, recommendation: Dict) -> Tuple[str, str]:
        """
        Validate a proposed change.

        Returns: (status, reason)
            status: "AUTO_APPLY", "NEEDS_REVIEW", "REJECTED", "DOCUMENT_ONLY"
            reason: explanation
        """
        change_type = recommendation.get("change", "")
        confidence = recommendation.get("confidence", 0.0)
        proposed_value = recommendation.get("proposed_value")

        # Check if forbidden
        for forbidden in self.guardrails["forbidden_changes"]:
            if forbidden.lower() in change_type.lower():
                return "REJECTED", f"Forbidden change type: {forbidden}"

        # Check if allowed
        allowed = False
        for allowed_pattern in self.guardrails["allowed_changes"]:
            if allowed_pattern.split("(")[0].strip().lower() in change_type.lower():
                allowed = True
                break

        if not allowed:
            return "NEEDS_REVIEW", "Change type not in allowed list"

        # Validate specific ranges
        if "duration" in change_type.lower():
            min_dur, max_dur = self.guardrails["safe_ranges"]["video_duration"]
            if not isinstance(proposed_value, (int, float)):
                return "NEEDS_REVIEW", "Duration must be numeric"
            if not (min_dur <= proposed_value <= max_dur):
                return "NEEDS_REVIEW", f"Duration {proposed_value} outside safe range [{min_dur}, {max_dur}]"

        if "media" in change_type.lower():
            if "max" in change_type.lower():
                min_val, max_val = self.guardrails["safe_ranges"]["max_media_items"][0], self.guardrails["safe_ranges"]["max_media_items"][1]
            else:
                min_val, max_val = self.guardrails["safe_ranges"]["min_media_items"][0], self.guardrails["safe_ranges"]["min_media_items"][1]

            if not isinstance(proposed_value, int):
                return "NEEDS_REVIEW", "Media count must be integer"
            if not (min_val <= proposed_value <= max_val):
                return "NEEDS_REVIEW", f"Media count {proposed_value} outside safe range [{min_val}, {max_val}]"

        if "tone" in change_type.lower():
            if not isinstance(proposed_value, str):
                return "NEEDS_REVIEW", "Tone must be string"
            if len(proposed_value) > self.guardrails["safe_ranges"]["tone_description_max_length"]:
                return "NEEDS_REVIEW", f"Tone too long (max {self.guardrails['safe_ranges']['tone_description_max_length']} chars)"

            # Check for injection patterns
            dangerous_patterns = [
                r"exec\(",
                r"eval\(",
                r"__import__",
                r"subprocess",
                r"os\.",
                r"rm\s+-rf",
                r"<script>",
            ]
            for pattern in dangerous_patterns:
                if re.search(pattern, proposed_value, re.IGNORECASE):
                    return "REJECTED", f"Tone contains dangerous pattern: {pattern}"

        # Check confidence threshold
        thresholds = self.guardrails["confidence_thresholds"]
        if confidence >= thresholds["auto_apply"]:
            return "AUTO_APPLY", "High confidence and within guardrails"
        elif confidence >= thresholds["flag_for_review"]:
            return "NEEDS_REVIEW", "Medium confidence"
        else:
            return "DOCUMENT_ONLY", "Low confidence"

    def validate_all(self, recommendations: list) -> Dict:
        """Validate all recommendations."""
        results = {
            "auto_apply": [],
            "needs_review": [],
            "rejected": [],
            "document_only": []
        }

        for rec in recommendations:
            status, reason = self.validate_change(rec)
            rec["validation_status"] = status
            rec["validation_reason"] = reason

            if status == "AUTO_APPLY":
                results["auto_apply"].append(rec)
            elif status == "NEEDS_REVIEW":
                results["needs_review"].append(rec)
            elif status == "REJECTED":
                results["rejected"].append(rec)
            else:
                results["document_only"].append(rec)

        return results


def main():
    """Test change guardian."""
    guardian = ChangeGuardian()

    test_cases = [
        {
            "change": "video_duration",
            "current_value": 60,
            "proposed_value": 55,
            "confidence": 0.85,
            "rationale": "Shorter videos have better retention"
        },
        {
            "change": "tone adjustments",
            "current_value": "energetic",
            "proposed_value": "calm and contemplative",
            "confidence": 0.75,
            "rationale": "Calmer tone might work better"
        },
        {
            "change": "API key update",
            "current_value": "xxx",
            "proposed_value": "yyy",
            "confidence": 0.9,
            "rationale": "Should be rejected"
        },
        {
            "change": "video_duration",
            "current_value": 60,
            "proposed_value": 200,
            "confidence": 0.9,
            "rationale": "Out of range"
        }
    ]

    results = guardian.validate_all(test_cases)

    print("Validation Results:")
    print(f"  Auto-apply: {len(results['auto_apply'])}")
    print(f"  Needs review: {len(results['needs_review'])}")
    print(f"  Rejected: {len(results['rejected'])}")
    print(f"  Document only: {len(results['document_only'])}")

    for rec in results["auto_apply"]:
        print(f"  ✓ {rec['change']}: {rec['validation_reason']}")

    for rec in results["rejected"]:
        print(f"  ✗ {rec['change']}: {rec['validation_reason']}")


if __name__ == "__main__":
    main()
