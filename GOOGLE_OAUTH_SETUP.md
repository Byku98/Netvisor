# Google OAuth Setup Guide

## Issue: "The given origin is not allowed for the given client ID"

You need to configure your Google Cloud Console OAuth 2.0 Client to allow the frontend origin.

### Steps to Fix:

1. **Go to Google Cloud Console**
   - Visit: https://console.cloud.google.com/apis/credentials
   - Find your OAuth 2.0 Client ID: `691478820434-oji7cm9qnujatpdmffcg69ak53t9tjsu`

2. **Add Authorized JavaScript Origins**
   - Click on the OAuth 2.0 Client ID to edit it
   - Under "Authorized JavaScript origins", add:
     - `http://localhost:5173` (for Vite dev server)
     - `http://localhost:3000` (for production if needed)

3. **Add Authorized Redirect URIs**
   - Under "Authorized redirect URIs", add:
     - `http://localhost:5173` (this is where Google will redirect after auth)

4. **Save the changes**
   - It may take a few minutes for the changes to propagate

## Issue: "Cross-Origin-Opener-Policy policy would block the window.postMessage call"

This is a browser security warning that's expected with OAuth 2.0 flows. It won't prevent authentication from working, but can be addressed if needed.

### Optional Fix:

In your `netvisor-frontend/index.html`, add a meta tag:
```html
<meta http-equiv="Cross-Origin-Opener-Policy" content="same-origin-allow-popups">
```

## Backend Configuration ✅ FIXED

The backend now correctly loads environment variables from `.env` file, so the Google Client ID is properly configured.

## Testing After Setup

Once you've configured Google Cloud Console:

1. Refresh your frontend at `http://localhost:5173`
2. Try Google Sign-In button
3. The 503 error should be resolved
4. You may still see the Cross-Origin-Opener-Policy warning (which is harmless)

## Current Status

✅ Backend proxy configuration fixed with enhanced logging
✅ Backend environment variable loading fixed
✅ Backend Google Client ID properly configured
⚠️ Google Cloud Console needs `http://localhost:5173` added as authorized origin