"""
Run once to generate gmail_token.json:
  python auth_gmail.py
"""
from google_auth_oauthlib.flow import InstalledAppFlow
import json

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

flow = InstalledAppFlow.from_client_secrets_file("gmail_oauth.json", SCOPES)
creds = flow.run_local_server(port=0)

with open("gmail_token.json", "w") as f:
    f.write(creds.to_json())

print("✅ gmail_token.json saved successfully.")
