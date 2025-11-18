# Fix "Access blocked: Youtube Automation has not completed the Google verification process"

This error occurs because your OAuth app is in "Testing" mode and you haven't added yourself as a test user.

## Quick Fix (5 minutes)

### Step 1: Go to OAuth Consent Screen

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (the one where you created YouTube API credentials)
3. Navigate to: **APIs & Services** → **OAuth consent screen**

### Step 2: Add Test Users

1. Scroll down to **Test users** section
2. Click **+ ADD USERS**
3. Enter your email: `ethantrokie@gmail.com`
4. Click **SAVE**

### Step 3: Try Upload Again

```bash
./upload_to_youtube.sh --privacy=private
```

The authorization should now work!

---

## Alternative: Publish the App (Optional)

If you don't want to add test users every time:

1. On the **OAuth consent screen** page
2. Click **PUBLISH APP** button
3. Click **CONFIRM**

**Note**: For personal use, staying in "Testing" mode is fine. Published apps require Google verification for certain scopes, but Testing mode allows you to use the app with approved test users.

---

## Why This Happens

- OAuth apps default to "Testing" mode for security
- Testing mode only allows pre-approved test users
- Your own email must be explicitly added as a test user
- This is a Google security feature to prevent unauthorized API access

---

## After Adding Test User

Once you've added yourself as a test user:

1. The OAuth flow will work normally
2. You'll see the consent screen asking for permissions
3. Click "Continue" → "Allow"
4. The token will be saved for future uploads
5. No need to re-authorize for 7 days (or longer if you use refresh tokens)
