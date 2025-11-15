#!/bin/bash

echo "🧪 Testing Educational Video Pipeline"
echo "======================================"
echo ""

# Note: This test requires Suno API key to be configured
# and will actually generate a video, incurring API costs (~$0.02-$0.04)

echo "⚠️  WARNING: This test will use the Suno API and incur costs"
echo "Press Ctrl+C to cancel, or Enter to continue..."
read

# Test with photosynthesis example
echo "Test 1: Photosynthesis (Express Mode)"
echo "--------------------------------------"
cp examples/photosynthesis.txt input/idea.txt
./pipeline.sh --express

if [ -f "outputs/final_video.mp4" ]; then
    echo "✅ Test 1 passed!"
    mv outputs/final_video.mp4 outputs/test_photosynthesis.mp4
else
    echo "❌ Test 1 failed - no video generated"
    exit 1
fi

echo ""
echo "All tests passed! 🎉"
echo ""
echo "Generated test videos:"
ls -lh outputs/test_*.mp4
