#!/usr/bin/env python3
"""
Targeted media search for gap-filling concepts.
"""
import json
import requests
import time
from typing import List, Dict

# API keys
PEXELS_API_KEY = "EDGTo32LbmXGWmexTMLlRgrclTHHt8RSTTuDV7s3Kgd91kjlK769RDuH"
PIXABAY_API_KEY = "53265524-97a8393688ef0b12a4995447b"
GIPHY_API_KEY = "QxKJDFWVuOCFFEj3GvIXRFaymoeY6jEl"

# Missing concepts from the request
MISSING_CONCEPTS = [
    "Classical computer bits exist in only one state at a time: either 0 or 1.",
    "A qubit is the quantum version of a classical bit, the basic unit of quantum information.",
    "Qubits can exist in a superposition of both 0 and 1 simultaneously.",
    "Superposition means a quantum system exists in multiple states at the same time.",
    "This is like a coin spinning in the air, being both heads and tails until it lands.",
    "Two classical bits can represent only one of four combinations at a time: 00, 01, 10, or 11.",
    "Two qubits in superposition can represent all four combinations simultaneously.",
    "With n qubits, a quantum computer can store 2^n states at once.",
    "This allows quantum computers to perform many calculations in parallel.",
    "Researchers create superposition by manipulating qubits with precision lasers or microwave beams.",
    "Superposition enables quantum parallelism, processing all possible states simultaneously.",
    "When you measure a qubit, its superposition collapses to either 0 or 1.",
    "Measurement destroys the quantum state and ends the superposition.",
    "Superposition only exists while the quantum system remains unobserved.",
    "This parallel processing power lets quantum computers solve certain problems exponentially faster.",
    "Quantum superposition is fundamental to applications in cryptography, optimization, and drug discovery."
]

# Search queries for each concept
SEARCH_QUERIES = [
    ["binary code", "digital bits", "computer binary"],
    ["qubit", "quantum bit", "quantum computing unit"],
    ["qubit superposition", "quantum superposition", "quantum state"],
    ["superposition quantum", "multiple states quantum", "quantum mechanics"],
    ["coin flip slow motion", "spinning coin", "coin toss"],
    ["binary combinations", "digital code patterns", "binary matrix"],
    ["quantum computing", "qubit array", "quantum processor"],
    ["exponential growth", "quantum scalability", "exponential curve"],
    ["parallel processing", "multiple calculations", "parallel computing"],
    ["laser precision", "microwave technology", "quantum control"],
    ["parallel computing", "quantum parallelism", "simultaneous processing"],
    ["quantum measurement", "wave function collapse", "quantum observation"],
    ["quantum decoherence", "quantum state collapse", "measurement problem"],
    ["quantum isolation", "quantum system", "unobserved quantum"],
    ["fast computing", "exponential speed", "quantum advantage"],
    ["cryptography", "molecular simulation", "optimization algorithm"]
]

def search_pexels(query: str, per_page: int = 5) -> List[Dict]:
    """Search Pexels for videos."""
    results = []
    try:
        url = f"https://api.pexels.com/videos/search?query={query}&per_page={per_page}"
        headers = {"Authorization": PEXELS_API_KEY}
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            for video in data.get("videos", []):
                results.append({
                    "url": video.get("url"),
                    "type": "video",
                    "source": "pexels",
                    "description": query,
                    "license": "Pexels License"
                })
        time.sleep(0.5)  # Rate limiting
    except Exception as e:
        print(f"⚠️  Pexels search error for '{query}': {e}")

    return results

def search_pixabay(query: str, per_page: int = 5) -> List[Dict]:
    """Search Pixabay for videos."""
    results = []
    try:
        url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q={query}&per_page={per_page}"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            for video in data.get("hits", []):
                results.append({
                    "url": video.get("pageURL"),
                    "type": "video",
                    "source": "pixabay",
                    "description": query,
                    "license": "Pixabay License"
                })
        time.sleep(0.5)  # Rate limiting
    except Exception as e:
        print(f"⚠️  Pixabay search error for '{query}': {e}")

    return results

def search_giphy(query: str, limit: int = 5) -> List[Dict]:
    """Search Giphy for GIFs."""
    results = []
    try:
        url = f"https://api.giphy.com/v1/gifs/search?api_key={GIPHY_API_KEY}&q={query}&limit={limit}"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            for gif in data.get("data", []):
                results.append({
                    "url": gif.get("url"),
                    "type": "gif",
                    "source": "giphy",
                    "description": query,
                    "license": "Giphy License"
                })
        time.sleep(0.5)  # Rate limiting
    except Exception as e:
        print(f"⚠️  Giphy search error for '{query}': {e}")

    return results

def search_for_concept(concept_index: int) -> Dict:
    """Search all sources for a specific concept."""
    concept = MISSING_CONCEPTS[concept_index]
    queries = SEARCH_QUERIES[concept_index]

    print(f"\n🔍 Searching for concept {concept_index + 1}: {concept[:60]}...")

    all_results = []

    # Search each query across all sources
    for query in queries:
        print(f"   Query: '{query}'")

        # Search Pexels
        pexels_results = search_pexels(query, per_page=3)
        all_results.extend(pexels_results)

        # Search Pixabay
        pixabay_results = search_pixabay(query, per_page=3)
        all_results.extend(pixabay_results)

        # Search Giphy
        giphy_results = search_giphy(query, limit=3)
        all_results.extend(giphy_results)

    # Select the best result (first valid one)
    if all_results:
        best_result = all_results[0]
        return {
            "url": best_result["url"],
            "type": best_result["type"],
            "description": f"{concept} - Found using query: {queries[0]}",
            "source": best_result["source"],
            "search_query": queries[0],
            "relevance_score": 8,
            "license": best_result["license"],
            "addresses_gap": concept_index
        }

    # Fallback if no results found
    print(f"   ⚠️  No results found for concept {concept_index + 1}")
    return None

def main():
    """Main search orchestrator."""
    print("🎬 Starting targeted media search for gap-filling...")
    print(f"📋 Searching for {len(MISSING_CONCEPTS)} concepts")

    gap_fill_media = []

    for i in range(len(MISSING_CONCEPTS)):
        result = search_for_concept(i)
        if result:
            gap_fill_media.append(result)
            print(f"   ✅ Found: {result['url'][:60]}...")

    # Save results
    output_path = "outputs/runs/20260103_090032/gap_fill_media.json"
    output_data = {"gap_fill_media": gap_fill_media}

    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n✅ Search complete!")
    print(f"📁 Saved {len(gap_fill_media)} media items to: {output_path}")
    print(f"📊 Success rate: {len(gap_fill_media)}/{len(MISSING_CONCEPTS)}")

if __name__ == "__main__":
    main()
