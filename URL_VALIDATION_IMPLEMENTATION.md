# URL Validation Implementation

## Problem Solved

The research agent was generating URLs that looked correct but didn't actually exist (hallucinated URLs). This caused download failures with a ~47% failure rate.

**Root Cause**: The LLM has some real video IDs in its training data (from documentation, examples) and mixes these with plausible-looking fake IDs.

## Solution

Implemented a URL validation and replacement system that:
1. Validates each URL from research.json using fast HEAD requests
2. For invalid/hallucinated URLs, searches actual APIs for real replacements
3. Achieves 100% success rate by combining validated + replaced URLs

## Files Created

### 1. `agents/media_search_api.py`
Extends `StockPhotoResolver` with API search capabilities.

**Key Features**:
- Search Pexels, Pixabay, and Giphy APIs for real videos/GIFs
- Extract search terms from descriptions (removes stop words, prioritizes scientific terms)
- Filter results by duration (5-20s), quality (HD/1080p+), and orientation
- Quick URL validation using HEAD requests

**Main Methods**:
```python
class MediaSearcher(StockPhotoResolver):
    def search_videos(query, source='pexels', max_results=5,
                     min_duration=5.0, max_duration=20.0)
    def extract_search_terms(description, max_terms=4)
    def validate_url(url, media_type='video')
```

### 2. `agents/1.5_validate_urls.py`
Main validation script that processes research.json.

**Features**:
- Validates all URLs in research.json
- Replaces hallucinated URLs with real ones from APIs
- Preserves all metadata (description, recommended_fact, etc.)
- Provides detailed statistics on validation success

**Usage**:
```bash
# Validate latest run
./venv/bin/python agents/1.5_validate_urls.py

# Validate specific file
./venv/bin/python agents/1.5_validate_urls.py outputs/runs/20251215_000214/research.json

# Quiet mode (less output)
./venv/bin/python agents/1.5_validate_urls.py research.json --quiet
```

### 3. `tests/test_url_validation.py`
Comprehensive test suite covering:
- Search term extraction (3 test cases)
- URL validation (3 test cases)
- API search functionality (3 APIs tested)
- Full validation flow (end-to-end test)

**Run Tests**:
```bash
./venv/bin/python tests/test_url_validation.py
```

## Pipeline Integration

The URL validator is automatically called after research (Stage 1.5):

```bash
Stage 1: Research
  -> Research agent generates media suggestions with URLs

Stage 1.5: URL Validation (NEW)
  -> Validates each URL
  -> Replaces hallucinated URLs with real ones from APIs
  -> Updates research.json with 100% valid URLs

Stage 2: Visual Ranking
  -> Proceeds with validated URLs
```

## Test Results

### Unit Tests
```
✅ PASS - Search Term Extraction (3/3 tests)
✅ PASS - URL Validation (3/3 tests)
✅ PASS - API Search (3/3 tests)
✅ PASS - Full Validation Flow (1/1 test)

Overall: 4/4 test suites passed
```

### Real-World Validation
Tested on actual research.json from run `20251215_000214`:

```
Total URLs:       31
✅ Validated:     17 (54.8%)  # Real URLs from LLM's training data
🔄 Replaced:      14 (45.2%)  # Hallucinated URLs replaced with real ones
❌ Failed:        0 (0.0%)    # No failures!

🎯 Success Rate:  100.0%
```

**Impact**: Improved from ~57% download success to 100% URL validity.

## How It Works

### 1. URL Validation
```python
# Quick HEAD request to check if URL exists
is_valid = searcher.validate_url(url, media_type)
```

### 2. Search Term Extraction
```python
# From: "Animated photon particle traveling through space with glowing energy"
# To: "animated photon particle traveling"

# Removes stop words, prioritizes longer scientific terms
search_query = searcher.extract_search_terms(description, max_terms=4)
```

### 3. API Search with Fallback
```python
# Try preferred source first (based on original URL)
results = searcher.search_videos(
    search_query,
    source='pexels',
    max_results=3,
    min_duration=5.0,
    max_duration=20.0
)

# Fallback to other sources if needed
if not results:
    results = searcher.search_videos(search_query, source='pixabay', ...)
```

### 4. Best Match Selection
- First result is usually most relevant (API ranking)
- Filters by duration (5-20s for educational content)
- Prefers HD quality (1080p+)
- Maintains landscape orientation

## API Rate Limits

- **Pexels**: 200 requests/hour (free tier)
- **Pixabay**: Unlimited with API key
- **Giphy**: 42 requests/hour (free tier)

With 30-40 URLs per run and fallback logic, these limits are sufficient.

## Configuration

API keys are configured in `config/.env`:
```bash
PEXELS_API_KEY=your_pexels_key
PIXABAY_API_KEY=your_pixabay_key
GIPHY_API_KEY=your_giphy_key
```

The `StockPhotoResolver` parent class handles loading these automatically.

## Future Improvements

1. **Caching**: Cache validated URLs to avoid re-validation
2. **Semantic Matching**: Use embeddings to find more semantically similar videos
3. **Quality Scoring**: Score replacements by relevance, duration, resolution
4. **Batch Validation**: Parallelize validation for faster processing

## Answer to "Why 57% Success?"

The LLM's 57% success rate with hallucinated URLs is explained by:

1. **Training Data Exposure**: The LLM saw real video IDs in:
   - API documentation examples
   - Tutorial code snippets
   - Crawled web pages with embedded videos

2. **Pattern Matching**: Some platforms (like Pexels) use sequential IDs, so random numbers have a chance of hitting real videos

3. **Popular Videos**: Well-known videos (Einstein portraits, atomic animations) are more likely to be in training data

This is why the solution needed API search - the LLM can't reliably generate valid URLs, but it can generate good search queries from descriptions!
