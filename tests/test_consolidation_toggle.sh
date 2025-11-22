#!/bin/bash
# Test clip consolidation toggle functionality

set -e

OUTPUT_DIR="outputs/runs/20251121_214448"

if [ ! -d "$OUTPUT_DIR" ]; then
    echo "❌ Test directory $OUTPUT_DIR not found"
    exit 1
fi

echo "🧪 Testing consolidation toggle..."
echo ""

# Test 1: Default mode (consolidation enabled)
echo "Test 1: Default mode (consolidation enabled)"
echo "============================================="
rm -f "$OUTPUT_DIR/synchronized_plan.json"
export OUTPUT_DIR
./venv/bin/python3 agents/5_assemble_video.py --resolution 1920x1080 > /tmp/consolidation_test1.log 2>&1
grep -E "Consolidating|Created.*consolidated|Using original" /tmp/consolidation_test1.log | head -3
CONSOLIDATED_CLIPS=$(jq '.total_shots' "$OUTPUT_DIR/synchronized_plan.json")
echo "  Result: $CONSOLIDATED_CLIPS clips created"
echo ""

# Test 2: No-consolidation mode
echo "Test 2: No-consolidation mode (--no-consolidation)"
echo "==================================================="
rm -f "$OUTPUT_DIR/synchronized_plan.json"
./venv/bin/python3 agents/5_assemble_video.py --resolution 1920x1080 --no-consolidation > /tmp/consolidation_test2.log 2>&1
grep -E "Consolidating|Created.*consolidated|Using original|DISABLED" /tmp/consolidation_test2.log | head -3
PHRASE_CLIPS=$(jq '.total_shots' "$OUTPUT_DIR/synchronized_plan.json")
echo "  Result: $PHRASE_CLIPS clips created"
echo ""

# Compare
echo "Comparison:"
echo "==========="
echo "  Consolidated mode: $CONSOLIDATED_CLIPS clips"
echo "  Phrase-level mode: $PHRASE_CLIPS clips"
echo ""

if [ "$CONSOLIDATED_CLIPS" -lt "$PHRASE_CLIPS" ]; then
    echo "✅ Test passed: Consolidation reduces clip count ($CONSOLIDATED_CLIPS < $PHRASE_CLIPS)"
else
    echo "❌ Test failed: Expected consolidation to reduce clip count"
    exit 1
fi
