"""
Login bharat.vistas using browser sessionid cookie.
Steps:
  1. Open chrome/firefox, go to instagram.com, log in as bharat.vistas
  2. Open DevTools (F12) → Application → Cookies → instagram.com
  3. Copy the value of 'sessionid' cookie
  4. Run: python login_by_cookie.py
  5. Paste the sessionid when prompted
"""
import json, sys
from instagrapi import Client
from pathlib import Path

sessionid = input("Paste your Instagram sessionid cookie: ").strip()
if not sessionid:
    print("No sessionid provided.")
    sys.exit(1)

print("Logging in with sessionid...")
cl = Client()
cl.delay_range = [2, 4]

try:
    cl.login_by_sessionid(sessionid)
    print(f"Login OK — @{cl.username}  user_id={cl.user_id}")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)

data = {"_instagrapi": cl.get_settings(), "user_id": str(cl.user_id)}
Path("ig_settings.json").write_text(json.dumps(data, indent=2))
print("\nSession saved to ig_settings.json")
print("\nNext — run:")
print("  gh secret set IG_SETTINGS_JSON --repo noreply-ooumph/ooumph_muggedmoments < ig_settings.json")
