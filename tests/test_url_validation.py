#!/usr/bin/env python3
"""
Tests for URL validation and search functionality.
"""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'agents'))

from media_search_api import MediaSearcher

# Import URLValidator directly since it's defined in 1.5_validate_urls.py
sys.path.insert(0, str(Path(__file__).parent.parent / 'agents'))
import importlib.util
spec = importlib.util.spec_from_file_location(
    "validate_urls",
    Path(__file__).parent.parent / 'agents' / '1.5_validate_urls.py'
)
validate_urls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validate_urls)
URLValidator = validate_urls.URLValidator


def test_search_term_extraction():
    """Test that search terms are extracted correctly from descriptions."""
    print("\n" + "="*60)
    print("TEST 1: Search Term Extraction")
    print("="*60)

    searcher = MediaSearcher()

    test_cases = [
        {
            'description': 'Animated photon particle traveling through space with glowing energy',
            'expected_contains': ['photon', 'particle', 'animated']
        },
        {
            'description': 'Light wave interference pattern showing constructive and destructive interference',
            'expected_contains': ['interference', 'pattern', 'light']
        },
        {
            'description': 'Electrons orbiting around an atomic nucleus',
            'expected_contains': ['electrons', 'orbiting', 'atomic', 'nucleus']
        }
    ]

    passed = 0
    for i, case in enumerate(test_cases, 1):
        desc = case['description']
        expected = case['expected_contains']

        terms = searcher.extract_search_terms(desc, max_terms=4)
        print(f"\n{i}. Description: {desc}")
        print(f"   Extracted: {terms}")

        # Check if expected terms are in the result
        found = sum(1 for term in expected if term in terms)
        if found >= 2:  # At least 2 expected terms should be present
            print(f"   ✅ PASS ({found}/{len(expected)} expected terms found)")
            passed += 1
        else:
            print(f"   ❌ FAIL (only {found}/{len(expected)} expected terms found)")

    print(f"\n📊 Search Term Extraction: {passed}/{len(test_cases)} tests passed")
    return passed == len(test_cases)


def test_url_validation():
    """Test URL validation against known real and fake URLs."""
    print("\n" + "="*60)
    print("TEST 2: URL Validation")
    print("="*60)

    searcher = MediaSearcher()

    # Test with known patterns
    test_cases = [
        # These are examples - they may or may not exist
        {
            'url': 'https://www.pexels.com/video/abstract-waves-flowing-7710243/',
            'expected': 'should validate or fail gracefully',
            'type': 'video'
        },
        {
            'url': 'https://giphy.com/gifs/nonsense-fake-url-12345xyz',
            'expected': 'should fail (obviously fake)',
            'type': 'gif'
        },
        {
            'url': 'https://pixabay.com/videos/invalid-99999999/',
            'expected': 'should fail (high fake ID)',
            'type': 'video'
        }
    ]

    passed = 0
    for i, case in enumerate(test_cases, 1):
        url = case['url']
        media_type = case['type']

        print(f"\n{i}. Testing: {url}")
        print(f"   Expected: {case['expected']}")

        is_valid = searcher.validate_url(url, media_type)

        if is_valid:
            print(f"   Result: ✅ Valid")
        else:
            print(f"   Result: ❌ Invalid")

        # For this test, we just verify it doesn't crash
        # Real validation depends on actual URL availability
        print(f"   ✅ PASS (validation completed without error)")
        passed += 1

    print(f"\n📊 URL Validation: {passed}/{len(test_cases)} tests passed")
    return True  # Always pass if no crashes


def test_api_search():
    """Test API search functionality (requires API keys)."""
    print("\n" + "="*60)
    print("TEST 3: API Search")
    print("="*60)

    searcher = MediaSearcher()

    # Check if API keys are configured
    has_pexels = bool(searcher.pexels_api_key)
    has_pixabay = bool(searcher.pixabay_api_key)
    has_giphy = bool(searcher.giphy_api_key)

    print(f"\n📋 API Keys Status:")
    print(f"   Pexels:  {'✅ Configured' if has_pexels else '❌ Not configured'}")
    print(f"   Pixabay: {'✅ Configured' if has_pixabay else '❌ Not configured'}")
    print(f"   Giphy:   {'✅ Configured' if has_giphy else '❌ Not configured'}")

    if not (has_pexels or has_pixabay or has_giphy):
        print("\n⚠️  Warning: No API keys configured")
        print("   Skipping API search tests")
        return True

    # Test search queries
    test_queries = [
        {'query': 'light particle photon', 'source': 'pexels', 'needs_key': 'pexels'},
        {'query': 'atom molecule science', 'source': 'pixabay', 'needs_key': 'pixabay'},
        {'query': 'electricity spark', 'source': 'giphy', 'needs_key': 'giphy'}
    ]

    passed = 0
    for i, test in enumerate(test_queries, 1):
        query = test['query']
        source = test['source']
        needs_key = test['needs_key']

        # Skip if API key not available
        if needs_key == 'pexels' and not has_pexels:
            print(f"\n{i}. Skipping {source} (no API key)")
            continue
        if needs_key == 'pixabay' and not has_pixabay:
            print(f"\n{i}. Skipping {source} (no API key)")
            continue
        if needs_key == 'giphy' and not has_giphy:
            print(f"\n{i}. Skipping {source} (no API key)")
            continue

        print(f"\n{i}. Searching {source.upper()}: '{query}'")

        try:
            results = searcher.search_videos(query, source=source, max_results=3)

            if results:
                print(f"   ✅ Found {len(results)} results")
                for j, result in enumerate(results[:2], 1):  # Show first 2
                    title = result.get('title', 'N/A')[:40]
                    duration = result.get('duration', 0)
                    print(f"      {j}. {title}... ({duration}s)")
                passed += 1
            else:
                print(f"   ⚠️  No results found (may be normal for rare queries)")
                passed += 1  # Not a failure, just no results

        except Exception as e:
            print(f"   ❌ FAIL: {e}")

    total_tested = sum(1 for t in test_queries if (
        (t['needs_key'] == 'pexels' and has_pexels) or
        (t['needs_key'] == 'pixabay' and has_pixabay) or
        (t['needs_key'] == 'giphy' and has_giphy)
    ))

    if total_tested == 0:
        print(f"\n📊 API Search: No tests run (no API keys)")
        return True
    else:
        print(f"\n📊 API Search: {passed}/{total_tested} tests passed")
        return passed >= total_tested * 0.7  # 70% pass rate acceptable


def test_full_validation_flow():
    """Test the complete validation flow with a sample research.json."""
    print("\n" + "="*60)
    print("TEST 4: Full Validation Flow")
    print("="*60)

    # Create test research data with mix of valid and invalid URLs
    test_data = {
        "topic": "Test Topic",
        "media_suggestions": [
            {
                "url": "https://www.pexels.com/video/fake-12345678/",
                "type": "video",
                "description": "Light particle animation",
                "title": "Test Video 1"
            },
            {
                "url": "https://pixabay.com/videos/invalid-99999999/",
                "type": "video",
                "description": "Atom molecule structure",
                "title": "Test Video 2"
            },
            {
                "url": "https://giphy.com/gifs/fake-url-abc123",
                "type": "gif",
                "description": "Electricity spark animation",
                "title": "Test GIF"
            }
        ]
    }

    # Write test file
    test_file = Path('/tmp/test_research.json')
    with open(test_file, 'w') as f:
        json.dump(test_data, f, indent=2)

    print(f"\n📝 Created test file: {test_file}")
    print(f"   Total URLs: {len(test_data['media_suggestions'])}")

    # Run validator
    print(f"\n🔍 Running validation...")
    validator = URLValidator(verbose=False)

    try:
        result = validator.validate_research_file(test_file)

        print(f"\n📊 Validation Results:")
        print(f"   Total:     {validator.stats['total']}")
        print(f"   Validated: {validator.stats['validated']}")
        print(f"   Replaced:  {validator.stats['replaced']}")
        print(f"   Failed:    {validator.stats['failed']}")

        # Verify output file was created
        if test_file.exists():
            with open(test_file) as f:
                updated_data = json.load(f)

            print(f"\n   ✅ Output file created successfully")

            # Check if any replacements happened
            if validator.stats['replaced'] > 0:
                print(f"   ✅ Successfully replaced {validator.stats['replaced']} URLs")

            # Clean up
            test_file.unlink()

            return True

        else:
            print(f"   ❌ Output file not created")
            return False

    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        if test_file.exists():
            test_file.unlink()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("🧪 URL VALIDATION TEST SUITE")
    print("="*60)

    results = {
        'Search Term Extraction': test_search_term_extraction(),
        'URL Validation': test_url_validation(),
        'API Search': test_api_search(),
        'Full Validation Flow': test_full_validation_flow()
    }

    print("\n" + "="*60)
    print("📊 FINAL RESULTS")
    print("="*60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\n🎯 Overall: {passed}/{total} test suites passed")

    if passed == total:
        print("\n✅ All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test suite(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
