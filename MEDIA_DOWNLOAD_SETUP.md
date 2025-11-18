# Media Download Setup Guide

## Current Status

The media download system has been updated with URL resolution to convert stock photo page URLs to direct download links.

### What Works Without API Keys

✅ **Pexels Images** - Working via web scraping (40% success rate in testing)
⚠️ **Unsplash Images** - Partial support, may have rate limits
❌ **Pexels Videos** - Requires API key
❌ **Pixabay Videos** - Requires better scraping or API

### Recommended: Use API Keys

For reliable downloads (especially videos), set up free API keys:

## Getting API Keys

### 1. Pexels API (Recommended)

1. Visit: https://www.pexels.com/api/
2. Click "Get Started" and create a free account
3. Copy your API key

**Rate Limits (Free):** 200 requests/hour, 20,000/month

### 2. Unsplash API (Optional but Helpful)

1. Visit: https://unsplash.com/developers
2. Create an account and register your application
3. Copy your Access Key (not Secret Key)

**Rate Limits (Free):** 50 requests/hour

### 3. Pixabay API (Optional)

1. Visit: https://pixabay.com/api/docs/
2. Create account and get API key

**Rate Limits (Free):** 100/minute, 5,000/hour

## Setting Up API Keys

### Method 1: Environment Variables (Recommended)

Add to your `~/.zshrc` or `~/.bash_profile`:

```bash
export PEXELS_API_KEY="your-pexels-api-key-here"
export UNSPLASH_API_KEY="your-unsplash-access-key-here"
export PIXABAY_API_KEY="your-pixabay-api-key-here"
```

Then reload: `source ~/.zshrc`

### Method 2: `.env` File

Create `.env` in project root:

```bash
PEXELS_API_KEY=your-pexels-api-key-here
UNSPLASH_API_KEY=your-unsplash-access-key-here
PIXABAY_API_KEY=your-pixabay-api-key-here
```

Add to `.gitignore`:
```bash
echo ".env" >> .gitignore
```

Then install python-dotenv:
```bash
./venv/bin/pip install python-dotenv
```

And add to `agents/stock_photo_api.py` at the top:
```python
from dotenv import load_dotenv
load_dotenv()
```

## Testing Your Setup

Test the resolver:
```bash
./venv/bin/python agents/stock_photo_api.py
```

Test full download:
```bash
./venv/bin/python agents/download_media.py
```

## Troubleshooting

### "No PEXELS_API_KEY set, using alternative method..."

This is normal - the system falls back to web scraping. For better reliability, add API keys.

### Downloads still failing

1. Check API key is set: `echo $PEXELS_API_KEY`
2. Verify key is valid by testing at the API docs
3. Check rate limits haven't been exceeded
4. Some older stock photo URLs may no longer be available

### Videos not downloading

Videos require API keys or very specific scraping patterns. For production use, **API keys are required** for video downloads.

## Alternative: Use Different Media Sources

If you don't want to set up API keys, you can:

1. Use only Pexels images (not videos)
2. Provide direct download URLs in the research data
3. Manually download media and place in `outputs/media/` with names `shot_01.jpg`, `shot_02.mp4`, etc.

## Next Steps

Once media downloads successfully, the pipeline will continue to:
- Stage 4.5: Human review and approval of media
- Stage 5: Video assembly with MoviePy
