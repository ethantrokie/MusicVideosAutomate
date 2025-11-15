# Setup Guide

Complete guide to setting up the Educational Video Automation System.

## Prerequisites

### Required Software

1. **macOS** (tested on Mac Studio, should work on other Macs)
2. **Python 3.9 or higher**
   ```bash
   python3 --version
   ```
3. **Claude Code CLI** (subscription required)
   - Download from: https://claude.ai/code
   - Verify installation: `claude --version`
4. **Homebrew** (for dependencies)
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

### Required Accounts

1. **Suno API** (for music generation)
   - Sign up: https://sunoapi.org
   - Cost: ~$0.02-$0.04 per song

2. **Optional: Media API Keys** (for better media access)
   - Pexels: https://www.pexels.com/api/
   - Pixabay: https://pixabay.com/api/docs/
   - Unsplash: https://unsplash.com/developers

---

## Installation Steps

### Step 1: Clone Repository

```bash
cd ~/SoftwareDevProjects
git clone <your-repo-url> MusicVideosAutomate
cd MusicVideosAutomate
```

### Step 2: Run Setup Script

```bash
./setup.sh
```

This will:
- Check all prerequisites
- Install `viu` (terminal image viewer)
- Create Python virtual environment
- Install Python dependencies

### Step 3: Configure API Keys

1. Open `config/config.json` in a text editor:
   ```bash
   nano config/config.json
   ```

2. Add your Suno API key:
   ```json
   {
     "suno_api": {
       "base_url": "https://api.sunoapi.org",
       "api_key": "sk_your_actual_api_key_here"
     }
   }
   ```

3. Save and close (Ctrl+O, Enter, Ctrl+X in nano)

---

## First Run

### Create Your First Video

1. **Write your idea**:
   ```bash
   echo "Explain how bees make honey. Tone: sweet and informative" > input/idea.txt
   ```

2. **Run the pipeline**:
   ```bash
   ./pipeline.sh
   ```

3. **Wait for completion** (typically 5-10 minutes)

4. **Watch your video**:
   ```bash
   open outputs/final_video.mp4
   ```

### Express Mode (Skip Review)

Once you trust the system:
```bash
./pipeline.sh --express
```

---

## Cost Estimation

### Per Video

| Component | Cost |
|-----------|------|
| Claude Code | $0.00 (included in subscription) |
| Suno API | $0.02-$0.04 |
| **Total** | **$0.02-$0.04** |

### Monthly Costs

- **Weekly videos**: ~$0.08-$0.16/month
- **Daily videos**: ~$0.60-$1.20/month
