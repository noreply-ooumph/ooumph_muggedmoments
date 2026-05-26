"""
Run from GitHub Actions to create a cloud-IP instagrapi session.

Flow:
  1. Try cl.login() — if challenge fires, Instagram sends app notification
  2. Wait 90s for user to tap 'This was me' in Instagram app
  3. Check if the same cl instance is now authenticated (no new login needed)
  4. If authenticated → save session. If not → retry up to 3 times.
"""
import os, sys, json, time
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, ChallengeUnknownStep
from pathlib import Path

username = os.environ["IG_USERNAME"]
password = os.environ["IG_PASSWORD"]

print(f"Logging in as {username}...")
cl = Client()
cl.delay_range = [2, 4]

MAX_ATTEMPTS = 3
authenticated = False

for attempt in range(1, MAX_ATTEMPTS + 1):
    try:
        cl.login(username, password)
        authenticated = True
        print(f"Login OK  user_id={cl.user_id}")
        break
    except (ChallengeUnknownStep, ChallengeRequired) as e:
        print(f"\n[!] Challenge sent to Instagram app (attempt {attempt}/{MAX_ATTEMPTS})")
        print(f"[!]   1. Open Instagram app as @{username}")
        print(f"[!]   2. Tap 'This was me' on the suspicious login notification")
        print(f"[!]   3. Waiting 90 seconds for your approval...")
        time.sleep(90)
        # Check if the challenge was approved on the current cl instance
        # Do NOT call cl.login() again — each new login triggers a new challenge
        try:
            info = cl.account_info()
            cl.user_id = info.pk
            authenticated = True
            print(f"[+] Challenge approved! Active as @{info.username}")
            break
        except Exception as check_err:
            print(f"[!]   Not yet approved ({check_err})")
            if attempt >= MAX_ATTEMPTS:
                print("[!] All attempts exhausted.")
                print("[!] Open Instagram app → approve the notification → re-run login.yml")
                sys.exit(3)
            print(f"[!]   Sending new login challenge (attempt {attempt + 1}/{MAX_ATTEMPTS})...")
    except Exception as e:
        print(f"[!] Login error: {e}")
        sys.exit(1)

if not authenticated:
    sys.exit(3)

settings = cl.get_settings()
data = {"_instagrapi": settings, "user_id": str(cl.user_id)}
Path("ig_settings.json").write_text(json.dumps(data, indent=2))
print("ig_settings.json saved")
