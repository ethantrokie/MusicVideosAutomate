#!/bin/bash

set -e

echo "🎬 Educational Video Automation - Setup"
echo "========================================"

# Check prerequisites
echo "Checking prerequisites..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Install from https://www.python.org/"
    exit 1
fi
echo "✅ Python 3 found"

# Check Claude CLI
if ! command -v claude &> /dev/null; then
    echo "❌ Claude CLI not found. Install Claude Code from https://claude.ai/code"
    exit 1
fi
echo "✅ Claude CLI found"

# Check viu (terminal image viewer)
if ! command -v viu &> /dev/null; then
    echo "⚠️  viu not found. Installing via Homebrew..."
    if command -v brew &> /dev/null; then
        brew install viu
    else
        echo "❌ Homebrew not found. Install viu manually: brew install viu"
        exit 1
    fi
fi
echo "✅ viu found"

# Create Python virtual environment
echo ""
echo "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "📥 Downloading CLIP model (one-time, ~400MB)..."
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('clip-ViT-B-32')"

if [ $? -eq 0 ]; then
    echo "✅ CLIP model downloaded and cached"
else
    echo "⚠️  CLIP model download failed - will download on first use"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "1. Sign up for Suno API: https://sunoapi.org"
echo "2. Get your API key from the dashboard"
echo "3. Edit config/config.json and add your API key"
echo "4. (Optional) Add API keys for Pexels/Pixabay/Unsplash for better media access"
echo ""
echo "Then run: ./pipeline.sh"
