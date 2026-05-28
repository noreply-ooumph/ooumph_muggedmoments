"""
Graph API replier for thegurukul.online — uses official Meta Graph API.
Never gets blocked. Runs via GitHub Actions cron every 30 minutes.
"""
import sys, os, time, json, random
sys.path.insert(0, os.path.dirname(__file__))

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env", override=True)

import requests
from ig_brain.groq_client import GroqClientWrapper
from ig_brain.config import GROQ_KEY, ACCOUNT_USERNAME, REPLY_SLEEP_MIN, REPLY_SLEEP_MAX, REPLIED_FILE
from ig_brain.replier import load_replied, save_replied

GRAPH_BASE     = "https://graph.facebook.com/v21.0"
PAGE_TOKEN     = os.environ.get("GRAPH_PAGE_TOKEN", "")
IG_USER_ID     = os.environ.get("GRAPH_IG_USER_ID", "17841467149837324")   # thegurukul.online

REPLY_SYSTEM = """Reply to an Instagram comment for muggedmoments (coffee culture, aesthetic mugs, cozy lifestyle).
1 sentence only. No filler words. No "Thanks!", "Great!", "Love this!". Direct, warm, on-topic. Emoji only if it adds meaning."""

MAX_POSTS  = 5    # scan 5 most recent posts
MAX_REPLIES = 10  # max replies per run
CHECKS     = 1    # single check per run — cron handles frequency
INTERVAL   = 60

client_ai = GroqClientWrapper(api_key=GROQ_KEY)


def graph_get(path, params=None):
    params = params or {}
    params["access_token"] = PAGE_TOKEN
    r = requests.get(f"{GRAPH_BASE}/{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def get_recent_media():
    data = graph_get(f"{IG_USER_ID}/media", {"fields": "id,caption,timestamp", "limit": MAX_POSTS})
    return data.get("data", [])


def get_comments(media_id):
    data = graph_get(f"{media_id}/comments", {"fields": "id,text,username,timestamp", "limit": 50})
    return data.get("data", [])


def post_reply(comment_id, message):
    r = requests.post(
        f"{GRAPH_BASE}/{comment_id}/replies",
        data={"message": message, "access_token": PAGE_TOKEN},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def generate_reply(comment_text, caption):
    resp = client_ai.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=40,
        system=REPLY_SYSTEM,
        messages=[{"role": "user", "content": f"Post topic: {caption[:80]}\nComment: {comment_text}\n\nReply:"}]
    )
    return resp.content[0].text.strip().strip('"').strip("'")


if not PAGE_TOKEN:
    print("[REPLIER] ERROR: GRAPH_PAGE_TOKEN not set — cannot authenticate")
    sys.exit(1)

print(f"[REPLIER] Graph API replier starting: {CHECKS} checks x {INTERVAL}s")

for check_num in range(1, CHECKS + 1):
    print(f"\n--- Check {check_num}/{CHECKS} ---")
    replied   = load_replied()
    new_total = 0

    try:
        posts = get_recent_media()
        print(f"  Found {len(posts)} recent posts")

        for post in posts[:MAX_POSTS]:
            if new_total >= MAX_REPLIES:
                print(f"  Max replies per run ({MAX_REPLIES}) reached — stopping.")
                break

            media_id = post["id"]
            caption  = post.get("caption", "")
            print(f"  Post {media_id[:12]}...", end="")

            try:
                comments = get_comments(media_id)
                fresh    = [c for c in comments if str(c["id"]) not in replied and c.get("text", "").strip()]
                print(f" {len(fresh)} new comments")

                for c in fresh:
                    if new_total >= MAX_REPLIES:
                        break
                    print(f"    @{c['username']}: {c['text'][:60]}")
                    try:
                        reply_text = generate_reply(c["text"], caption)
                        print(f"    Reply: {reply_text}")
                        post_reply(c["id"], reply_text)
                        replied.add(str(c["id"]))
                        save_replied(replied)
                        new_total += 1
                        print(f"    Replied OK")
                        time.sleep(random.randint(REPLY_SLEEP_MIN, REPLY_SLEEP_MAX))
                    except requests.HTTPError as e:
                        print(f"    Reply HTTP error: {e.response.status_code} {e.response.text[:100]}")
                        time.sleep(10)
                    except Exception as e:
                        print(f"    Reply error: {e}")
                        time.sleep(10)

            except requests.HTTPError as e:
                print(f" HTTP {e.response.status_code}: {e.response.text[:100]}")
            except Exception as e:
                print(f" error: {e}")

    except requests.HTTPError as e:
        print(f"  Graph API error: {e.response.status_code} {e.response.text[:150]}")
    except Exception as e:
        print(f"  Check error: {e}")

    print(f"  Done. Replied to {new_total} new comments this check.")
    if check_num < CHECKS:
        print(f"  Waiting {INTERVAL}s...")
        time.sleep(INTERVAL)

print(f"\n[REPLIER] Loop complete.")
