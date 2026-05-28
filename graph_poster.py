"""
Graph API poster — two steps:
  python graph_poster.py --step generate   → create image + save pending_post.json
  python graph_poster.py --step publish    → post to Instagram via Graph API
# thegurukul.online
"""
import sys, os, json, time, argparse, requests
sys.path.insert(0, os.path.dirname(__file__))

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env", override=True)

from datetime import datetime
from ig_brain.groq_client import GroqClientWrapper
from ig_brain.config import GROQ_KEY
from ig_brain.memory import load_posted, record_post
from ig_brain.master_agent import sync_metrics, maybe_evolve, generate_content
from ig_brain.image_gen_pending import generate_pending_image

GRAPH_BASE  = "https://graph.facebook.com/v21.0"
PAGE_TOKEN  = os.environ.get("GRAPH_PAGE_TOKEN", "")
IG_USER_ID  = os.environ.get("GRAPH_IG_USER_ID", "17841467149837324")
REPO_RAW    = "https://raw.githubusercontent.com/noreply-ooumph/Ooumph_Gurukul/main"
PENDING_FILE = Path(__file__).parent / "pending_post.json"

client = GroqClientWrapper(api_key=GROQ_KEY)


def step_generate():
    print("[POSTER] Step 1: Generate content + image")

    # Sync real metrics from Graph API
    if PAGE_TOKEN:
        sync_metrics(IG_USER_ID, PAGE_TOKEN)

    # Evolve strategy if due (every 5 posts)
    maybe_evolve(client)

    # Generate content
    print("  [CONTENT AGENT] Generating post...")
    content = generate_content(client)
    topic       = content.get("topic", "")
    caption     = content.get("caption", "")
    hashtags    = content.get("hashtags", [])
    img_prompt  = content.get("image_prompt", topic)
    pillar      = content.get("pillar", "")

    print(f"  Topic: {topic}")
    print(f"  Caption: {caption[:80]}...")

    full_caption = caption + "\n\n" + " ".join(hashtags)

    # Generate image → pending_post.jpg
    generate_pending_image(img_prompt)

    # Save pending post data
    pending = {
        "topic": topic, "pillar": pillar,
        "caption": full_caption,
        "hashtags": hashtags,
        "image_prompt": img_prompt,
        "generated_at": datetime.utcnow().isoformat(),
    }
    PENDING_FILE.write_text(json.dumps(pending, indent=2), encoding="utf-8")
    print("[POSTER] Step 1 complete — pending_post.jpg + pending_post.json saved.")


def step_publish():
    print("[POSTER] Step 2: Publish to Instagram via Graph API")

    if not PAGE_TOKEN:
        print("  ERROR: GRAPH_PAGE_TOKEN not set")
        sys.exit(1)

    if not PENDING_FILE.exists():
        print("  ERROR: pending_post.json not found — run --step generate first")
        sys.exit(1)

    pending     = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    caption     = pending["caption"]
    topic       = pending["topic"]
    hashtags    = pending.get("hashtags", [])
    image_url   = f"{REPO_RAW}/generated_images/pending_post.jpg"

    print(f"  Image URL: {image_url}")

    # Step A: Create media container
    print("  Creating media container...")
    r = requests.post(
        f"{GRAPH_BASE}/{IG_USER_ID}/media",
        data={"image_url": image_url, "caption": caption, "access_token": PAGE_TOKEN},
        timeout=60,
    )
    if not r.ok:
        print(f"  Container error: {r.status_code} {r.text[:200]}")
        sys.exit(1)

    creation_id = r.json().get("id")
    print(f"  Container ID: {creation_id}")

    # Wait for container to be ready
    time.sleep(5)

    # Step B: Publish
    print("  Publishing...")
    r2 = requests.post(
        f"{GRAPH_BASE}/{IG_USER_ID}/media_publish",
        data={"creation_id": creation_id, "access_token": PAGE_TOKEN},
        timeout=30,
    )
    if not r2.ok:
        print(f"  Publish error: {r2.status_code} {r2.text[:200]}")
        sys.exit(1)

    media_id = r2.json().get("id", "")
    print(f"  Published! Media ID: {media_id}")

    # Record post
    record_post(media_id, media_id, topic, caption, hashtags)
    PENDING_FILE.unlink(missing_ok=True)
    print("[POSTER] Step 2 complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", choices=["generate", "publish"], required=True)
    args = parser.parse_args()

    # Check already posted today
    posted = load_posted()
    today  = datetime.utcnow().strftime("%Y-%m-%d")
    if any(p.get("posted_at", "")[:10] == today for p in posted):
        print(f"[POSTER] Already posted today ({today}). Exiting.")
        sys.exit(0)

    if args.step == "generate":
        step_generate()
    elif args.step == "publish":
        step_publish()
