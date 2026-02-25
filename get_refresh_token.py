"""
get_refresh_token.py — Generate Google OAuth2 refresh_token
============================================================
Uses your GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET from .env
to open a browser login and print the refresh_token.

Run: python get_refresh_token.py
"""

import os
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv(".env")

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send",
]

client_id     = os.getenv("GOOGLE_CLIENT_ID", "").strip()
client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()

if not client_id or not client_secret:
    print("\n❌ GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET missing in .env")
    print("   Add them and re-run this script.\n")
    exit(1)

# Build the client config inline — no JSON file needed
client_config = {
    "installed": {
        "client_id":     client_id,
        "client_secret": client_secret,
        "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
        "token_uri":     "https://oauth2.googleapis.com/token",
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
    }
}

print("\nBrowser khul raha hai — Google account se login karo...")
flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

print("\n" + "=" * 55)
print("  ✅ Refresh token mil gaya! .env mein add karo:")
print("=" * 55)
print(f"\nGOOGLE_REFRESH_TOKEN={creds.refresh_token}\n")
print("=" * 55 + "\n")
