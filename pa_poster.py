"""
GitHub Actions Poster — posts once per day at the first matching hour.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env", override=True)

from datetime import datetime
from ig_brain.config import GROQ_KEY
from ig_brain.groq_client import GroqClientWrapper
from ig_brain.planner import generate_content_plan
from ig_brain.poster import run_poster
from ig_brain.memory import load_posted

client = GroqClientWrapper(api_key=GROQ_KEY)
now    = datetime.utcnow()

print(f"[POSTER] Running at {now.strftime('%Y-%m-%d %H:%M')} UTC")

# 1 post per day — exit if already posted today
posted = load_posted()
today  = now.strftime("%Y-%m-%d")
if any(p.get("posted_at", "")[:10] == today for p in posted):
    print(f"[POSTER] Already posted today ({today}). Exiting.")
    sys.exit(0)

# Load or generate content plan
PLAN_FILE = Path(__file__).parent / "content_plan.json"
plan = json.loads(PLAN_FILE.read_text(encoding="utf-8")) if PLAN_FILE.exists() else []

if not plan:
    print("[POSTER] Generating new content plan...")
    plan = generate_content_plan(client, days=14)
    PLAN_FILE.write_text(json.dumps(plan, indent=2), encoding="utf-8")

# Take next topic
topic_data = plan.pop(0)
PLAN_FILE.write_text(json.dumps(plan, indent=2), encoding="utf-8")
print(f"[POSTER] Posting: {topic_data.get('topic')}")

def decode_shortcode(code: str) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    n = 0
    for c in code:
        n = n * 64 + alphabet.index(c)
    return str(n)

def save_to_posts_list(shortcode: str, caption: str = ""):
    pfile = Path(__file__).parent / "posts_list.json"
    posts = json.loads(pfile.read_text(encoding="utf-8")) if pfile.exists() else []
    if shortcode not in {p["code"] for p in posts}:
        posts.insert(0, {"id": decode_shortcode(shortcode), "code": shortcode, "caption": caption[:80]})
        pfile.write_text(json.dumps(posts, indent=2), encoding="utf-8")
        print(f"[POSTER] posts_list.json updated ({len(posts)} posts)")

try:
    shortcode = run_poster(client, topic_data)
    save_to_posts_list(shortcode, topic_data.get("topic", ""))
    print(f"[POSTER] Success: https://www.instagram.com/p/{shortcode}/")
except Exception as e:
    import traceback; traceback.print_exc()
    print(f"[POSTER] Error: {e}")
    plan.insert(0, topic_data)
    PLAN_FILE.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    sys.exit(1)
