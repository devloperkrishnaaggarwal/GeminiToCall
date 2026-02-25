"""
google_auth_setup.py — One-time OAuth2 setup for Raj Dental Care agent
=======================================================================
Run this ONCE on your local machine (not on VPS) to get a refresh_token.
It opens a browser → you log in with the clinic Google account → prints tokens.
Copy the output into your .env file.

Usage:
    python google_auth_setup.py
"""

import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send",
]

def main():
    print("\n" + "="*60)
    print("  Raj Dental Care — Google OAuth2 Setup")
    print("="*60)
    print("""
You need a 'client_secret.json' file from Google Cloud Console.

Steps to get it:
  1. Go to https://console.cloud.google.com/
  2. Create a new project (or select existing)
  3. Enable APIs:
       - Gmail API
       - Google Calendar API
  4. Go to 'APIs & Services' → 'Credentials'
  5. Click 'Create Credentials' → 'OAuth 2.0 Client IDs'
  6. Application type: Desktop app
  7. Download the JSON file and rename it to 'client_secret.json'
  8. Place it in this folder and run this script again.
""")

    if not os.path.exists("client_secret.json"):
        print("❌ client_secret.json not found in current directory.")
        print("   Follow the steps above and re-run this script.")
        return

    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    print("\n" + "="*60)
    print("  ✅ Success! Add these to your .env file:")
    print("="*60)
    print(f"\nGOOGLE_CLIENT_ID={creds.client_id}")
    print(f"GOOGLE_CLIENT_SECRET={creds.client_secret}")
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
    print("\n" + "="*60)
    print("  Then copy these into your VPS .env file too.")
    print("  You never need to run this script again!")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
