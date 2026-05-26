"""
GitHub Actions replier loop — uses instagrapi mobile API.
Runs 5 checks x 1 minute apart = 5 min window per run.
"""
import sys, os, time, json, random
sys.path.insert(0, os.path.dirname(__file__))

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env", override=True)

from ig_brain.groq_client import GroqClientWrapper
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ChallengeRequired

from ig_brain.config import GROQ_KEY, ACCOUNT_USERNAME, ACCOUNT_USER_ID, REPLY_SLEEP_MIN, REPLY_SLEEP_MAX, REPLIED_FILE
from ig_brain.replier import load_replied, save_replied, generate_reply

SETTINGS_FILE   = Path(__file__).parent / "ig_settings.json"
POSTS_LIST_FILE = Path(__file__).parent / "posts_list.json"

REPLY_SYSTEM = """You are the voice behind bharat.vistas, an Instagram page dedicated to Indian travel photography, landscapes, heritage sites, and the beauty of Bharat.

Reply to a comment on one of your posts. Rules:
- 1-2 sentences max
- Sound like a passionate travel photographer — vivid, evocative, adventurous
- If they asked about a destination or spot, be helpful and paint a picture with words
- If praise, be genuine and invite them to explore further
- If a question about travel or photography, give a crisp, inspiring answer
- Emojis are welcome — keep it warm and adventurous
- Never start with "Thanks for commenting!" or "Glad you liked it!"
- Vary sentence openers — don't always start with "We" or "I"
"""

def get_client() -> Client:
    """Load session from ig_settings.json. Validate it. Fall back to login if expired."""
    cl = Client()
    cl.delay_range = [1, 3]

    if not SETTINGS_FILE.exists():
        print("  ERROR: ig_settings.json not found — cannot authenticate")
        sys.exit(1)

    settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))

    if "_instagrapi" in settings:
        cl.set_settings(settings["_instagrapi"])
        uid = settings.get("user_id", "?")
        print(f"  Session loaded for user_id={uid}")

        # Validate session with a lightweight API call
        try:
            info = cl.account_info()
            print(f"  Session valid — logged in as @{info.username}")
            return cl
        except (LoginRequired, ChallengeRequired) as e:
            print(f"  Session EXPIRED or challenged: {e}")
            print("  --> Trigger login.yml manually or run do_login.py locally")
            print("  --> Then update IG_SETTINGS_JSON secret")
            sys.exit(2)
        except Exception as e:
            print(f"  Session validation warning: {e} — continuing anyway")
            return cl
    else:
        # Fallback: try direct login (may fail from cloud IP)
        username = os.environ.get("IG_USERNAME", ACCOUNT_USERNAME)
        password = os.environ.get("IG_PASSWORD", "")
        print(f"  No _instagrapi session found — attempting login as {username}")
        try:
            cl.login(username, password)
            print(f"  Login OK user_id={cl.user_id}")
            # Save new session back
            data = {"_instagrapi": cl.get_settings(), "user_id": str(cl.user_id)}
            SETTINGS_FILE.write_text(json.dumps(data, indent=2))
            print("  Session saved to ig_settings.json")
            return cl
        except (ChallengeRequired, LoginRequired) as e:
            print(f"  LOGIN FAILED (challenge from cloud IP): {e}")
            print("  --> Trigger login.yml workflow to create a cloud session")
            sys.exit(2)
        except Exception as e:
            print(f"  Login error: {e}")
            sys.exit(1)

def load_posts() -> list:
    if POSTS_LIST_FILE.exists():
        posts = json.loads(POSTS_LIST_FILE.read_text(encoding="utf-8"))
        print(f"  Loaded {len(posts)} posts from posts_list.json")
        return posts
    print("  WARNING: posts_list.json not found — no posts to check")
    return []

def generate_reply_text(client_ai, comment: str, caption: str) -> str:
    resp = client_ai.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        system=REPLY_SYSTEM,
        messages=[{"role": "user", "content": f"Post topic: {caption[:80]}\nComment: {comment}\n\nReply:"}]
    )
    return resp.content[0].text.strip().strip('"').strip("'")

client_ai = GroqClientWrapper(api_key=GROQ_KEY)
CHECKS        = 3    # 3 checks x 60s = 3 min window
MAX_POSTS     = 3    # only scan the 3 most recent posts
MAX_ERRORS    = 2    # stop immediately after this many rate-limit errors
INTERVAL = 60

print(f"[REPLIER] Starting: {CHECKS} checks x {INTERVAL}s — scanning last {MAX_POSTS} posts")

try:
    cl = get_client()
except SystemExit as e:
    sys.exit(e.code)

for check_num in range(1, CHECKS + 1):
    print(f"\n--- Check {check_num}/{CHECKS} ---")
    replied     = load_replied()
    posts       = load_posts()[:MAX_POSTS]
    new_total   = 0
    error_count = 0

    for post in posts:
        if error_count >= MAX_ERRORS:
            print(f"  Rate-limit threshold hit — stopping this run to protect the account.")
            break

        print(f"  Post {post['code']}...", end="")
        try:
            comments = cl.media_comments(post["id"], amount=50)
            fresh = []
            for c in comments:
                uid  = str(c.user.pk)
                text = c.text.strip()
                if uid == str(ACCOUNT_USER_ID):
                    continue
                if text.lower().startswith(f"@{ACCOUNT_USERNAME.lower()}"):
                    continue
                if str(c.pk) in replied:
                    continue
                if hasattr(c, 'child_comment_count') and c.child_comment_count > 0:
                    try:
                        children = cl.media_comment_replies(post["id"], str(c.pk))
                        if any(str(ch.user.pk) == str(ACCOUNT_USER_ID) for ch in children):
                            replied.add(str(c.pk))
                            continue
                    except Exception:
                        pass
                fresh.append(c)
            print(f" {len(fresh)} new comments")

            for c in fresh:
                print(f"    @{c.user.username}: {c.text[:50]}")
                try:
                    reply_text = generate_reply_text(client_ai, c.text, post.get("caption", ""))
                    print(f"    Reply: {reply_text}")
                    cl.media_comment(post["id"], reply_text, replied_to_comment_id=str(c.pk))
                    replied.add(str(c.pk))
                    save_replied(replied)
                    new_total += 1
                    print(f"    Replied OK")
                    time.sleep(random.randint(REPLY_SLEEP_MIN, REPLY_SLEEP_MAX))
                except Exception as e:
                    print(f"    Reply error: {e}")
                    time.sleep(10)

        except (LoginRequired, ChallengeRequired) as e:
            print(f"\n  SESSION ERROR: {e}")
            sys.exit(2)
        except Exception as e:
            err_str = str(e)
            print(f" error: {err_str[:80]}")
            if "feedback_required" in err_str or "Please wait" in err_str or "401" in err_str:
                error_count += 1
                print(f"  Rate-limit detected ({error_count}/{MAX_ERRORS}) — skipping remaining posts.")

    print(f"  Done. Replied to {new_total} new comments this check.")
    if error_count >= MAX_ERRORS:
        print(f"  Exiting early to avoid further rate-limiting.")
        break
    if check_num < CHECKS:
        print(f"  Waiting {INTERVAL}s...")
        time.sleep(INTERVAL)

print(f"\n[REPLIER] Loop complete.")

# Save updated session so tokens stay fresh for next run
try:
    updated = {"_instagrapi": cl.get_settings(), "user_id": str(cl.user_id)}
    SETTINGS_FILE.write_text(json.dumps(updated, indent=2))
    print("[REPLIER] Session state saved.")
except Exception as e:
    print(f"[REPLIER] Warning: session save failed: {e}")
