# Troubleshooting Guide

Common issues and solutions for the Educational Video Automation System.

---

## Setup Issues

### "Python 3 not found"

**Solutions**:
```bash
# Install Python via Homebrew
brew install python3
```

### "Claude CLI not found"

**Solutions**:
1. Install Claude Code from https://claude.ai/code
2. Restart terminal after installation

### "viu not found"

**Solutions**:
```bash
# Install via Homebrew
brew install viu
```

---

## Pipeline Errors

### Research Agent Fails

**Error**: "Claude Code returned invalid JSON"

**Solutions**:
```bash
# Test Claude CLI directly
claude -p "What is 2+2?" --output-format json
```

### Music Composition Fails

**Error**: "Suno API key not configured"

**Solutions**:
1. Check config file: `cat config/config.json`
2. Ensure API key is correct (starts with `sk_`)
3. Verify API account is active at sunoapi.org

### Video Assembly Fails

**Error**: "MoviePy encoding error"

**Solutions**:
```bash
# Ensure FFmpeg is installed
brew install ffmpeg

# Reinstall if needed
pip install --upgrade moviepy
```

---

## Getting Help

### Check Logs

```bash
# View latest log
ls -lt logs/
cat logs/pipeline_YYYYMMDD_HHMMSS.log
```

### Reset Everything

```bash
# Clean slate
rm -rf outputs/* logs/*
rm -rf venv

# Re-setup
./setup.sh
```
