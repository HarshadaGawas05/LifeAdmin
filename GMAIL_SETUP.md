# Gmail Integration Setup Guide

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Gmail API:
   - Go to "APIs & Services" > "Library"
   - Search for "Gmail API"
   - Click "Enable"

## Step 2: Create OAuth 2.0 Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth 2.0 Client IDs"
3. Choose "Web application"
4. Add authorized redirect URIs:
   - `http://localhost:3000/connect` (for development)
   - `http://localhost:8000/gmail/callback` (for API callback)
5. Copy the Client ID and Client Secret

## Step 3: Update Environment Variables

Add to your `.env` file:
```
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
```

## Step 4: Test Gmail Integration

1. Start the application: `docker-compose up -d`
2. Go to http://localhost:3000/connect
3. Click "Connect Gmail (Demo)" - this will use mock data for now
4. For real Gmail integration, the OAuth flow will be implemented

## Current Status

- ✅ Mock Gmail integration working
- ✅ Task parsing and storage working
- ✅ Dashboard displaying tasks
- 🔄 Real Gmail OAuth flow (in progress)

## Testing with Mock Emails

The system currently processes mock emails that simulate:
- Netflix subscription bills
- Spotify renewal notices
- Electricity bills
- Assignment reminders
- Job application updates

These are automatically parsed and converted to tasks with appropriate categories and priority scores.
