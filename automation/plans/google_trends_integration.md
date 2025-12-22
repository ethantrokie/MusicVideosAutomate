# Plan: Google Trends Integration for Topic Generation

## Overview

Integrate Google Trends data into the topic generation pipeline to make video topics more relevant to current search interests. Uses the `pytrends` library (unofficial Google Trends API for Python).

## Architecture

```
┌─────────────────────┐
│  topic_generator.py │
│    (modified)       │
└─────────┬───────────┘
          │ imports
          ▼
┌─────────────────────┐     ┌──────────────────┐
│  trends_fetcher.py  │────▶│  Google Trends   │
│      (new)          │     │   (pytrends)     │
└─────────────────────┘     └──────────────────┘
          │
          ▼
┌─────────────────────┐
│   Claude Prompt     │
│  (enhanced with     │
│   trending topics)  │
└─────────────────────┘
```

## Implementation Tasks

### Task 1: Add pytrends dependency
- Add `pytrends` to requirements.txt
- Install in venv

### Task 2: Create trends_fetcher.py module
Location: `automation/trends_fetcher.py`

Functions to implement:
- `get_trending_searches()` - Get real-time trending searches (US)
- `get_related_queries(seed_keywords)` - Get related queries for science/education seeds
- `get_trending_science_topics()` - Main function combining the above, filtered for educational content

Seed keywords to query:
- "science explained"
- "how does X work"
- "physics"
- "chemistry"
- "biology"
- "space"
- "technology"

### Task 3: Modify topic_generator.py
- Import trends_fetcher
- Call `get_trending_science_topics()` before generating topic
- Add trending topics to Claude prompt as inspiration/suggestions
- Add fallback if trends fetch fails (continue with existing behavior)

### Task 4: Add configuration options
Location: `automation/config/automation_config.json`

New config section:
```json
"trends": {
  "enabled": true,
  "seed_keywords": ["science", "physics", "chemistry", "biology", "how things work"],
  "max_trending_topics": 10,
  "cache_duration_hours": 6
}
```

### Task 5: Add caching (optional but recommended)
- Cache trends results for 6 hours to avoid rate limiting
- Store in `automation/state/trends_cache.json`

## Modified Claude Prompt (Example)

```
CURRENT TRENDING TOPICS (for inspiration):
- Why do batteries explode
- Northern lights 2024
- How solar panels work
- DNA testing explained
...

Generate a topic that either:
1. Directly addresses a trending topic above, OR
2. Is inspired by/related to current trends

[rest of existing prompt]
```

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Google rate limiting | Cache results for 6 hours |
| pytrends breaking (unofficial API) | Graceful fallback to existing behavior |
| Irrelevant trends | Filter by educational keywords |
| No trends available | Continue without trends data |

## Files Changed/Created

| File | Action |
|------|--------|
| `requirements.txt` | Add pytrends |
| `automation/trends_fetcher.py` | Create new |
| `automation/topic_generator.py` | Modify |
| `automation/config/automation_config.json` | Add trends config |
| `automation/state/trends_cache.json` | Create new (runtime) |

## Testing

1. Run `trends_fetcher.py` standalone to verify it fetches data
2. Run `topic_generator.py` to verify integration
3. Check that fallback works when trends unavailable
