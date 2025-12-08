# Setup Guide: Automate TikTok Posting with n8n, Zapier, and Buffer

This guide walks you through setting up the automation workflow to post videos to TikTok.

## Prerequisites
1.  **n8n**: Installed and running (you have this locally).
2.  **Zapier Account**: Free plan is sufficient for basic testing, but check limits for high volume.
3.  **Buffer Account**: Free plan.
4.  **TikTok Account**: Logged in on your mobile device (usually needed to connect Buffer).

## Step 1: Configure Buffer
1.  Log in to [Buffer](https://buffer.com/).
2.  Click "Add Channels" and select **TikTok**.
3.  Follow the prompts to authorize Buffer to access your TikTok account.

## Step 2: Create a Zap in Zapier
1.  Log in to [Zapier](https://zapier.com/).
2.  Click **Create Zap**.
3.  **Trigger**:
    *   Search for **Webhooks by Zapier**.
    *   Event: **Catch Hook**.
    *   Click Continue.
    *   **Copy the Webhook URL**. You will need this for n8n.
4.  **Action**:
    *   Search for **Buffer**.
    *   Event: **Add to Queue** (or "Create Status Update").
    *   Connect your Buffer account.
    *   **Profile**: Select your TikTok profile.
    *   **Text**: Map this to a field you'll send from n8n (e.g., `caption`).
    *   **Video**: Map this to the file URL or binary data field from the Webhook. *Note: Zapier handles file uploads best if n8n sends a public URL, but for local files, you might need to upload them to a cloud storage (like Google Drive) first in n8n, or try sending the binary directly if Zapier supports it for your plan.*
5.  **Test**: You'll need to send a test request from n8n to finish setting up the Zap.

## Step 3: Configure n8n
1.  Open your local n8n instance (usually `http://localhost:5678`).
2.  **Import Workflow**:
    *   Click "Workflows" -> "Import from File".
    *   Select the `n8n_tiktok_buffer_workflow.json` file created in your project directory.
3.  **Configure Nodes**:
    *   **Read Binary File**: Double-click and set the `File Path` to the absolute path of the video you want to upload.
    *   **Send to Zapier**:
        *   Double-click the node.
        *   Paste your **Zapier Webhook URL** into the `URL` field.
        *   Ensure "Send Binary Data" is toggled ON.
        *   Property Name: `data` (or whatever you want to call it).
        *   *Optional*: Add a Query Parameter or Body Parameter for the `caption` if you want to send text.

## Step 4: Run the Workflow
1.  Click **Execute Workflow** in n8n.
2.  Go back to Zapier and click **Test trigger**. It should find the request you just sent.
3.  Finish setting up the Buffer action in Zapier using the test data.
4.  **Publish** your Zap.

## Troubleshooting
*   **File Issues**: If Zapier doesn't receive the file correctly as binary, you may need to add a step in n8n to upload the video to Google Drive/Dropbox first, and then send the *public download link* to Zapier.
