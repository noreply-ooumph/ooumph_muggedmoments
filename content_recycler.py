#!/usr/bin/env python3
"""Content Recycler — reposts top-performing old posts once a month."""

import os, sys, json, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
import requests

load_dotenv()

GRAPH_BASE = "https://graph.facebook.com/v21.0"
TOKEN = os.environ["GRAPH_PAGE_TOKEN"]
IG_USER_ID = os.environ["GRAPH_IG_USER_ID"]
ACCOUNT_NAME = os.environ.get("ACCOUNT_NAME", "instagram")
USERNAME = os.environ.get("IG_USERNAME", ACCOUNT_NAME)

STATE_FILE = Path("recycled_posts.json")
MIN_AGE_DAYS = 90
RECYCLE_COOLDOWN_DAYS = 90


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_state(data: dict):
    STATE_FILE.write_text(json.dumps(data, indent=2))


def get_media(limit=50):
    url = f"{GRAPH_BASE}/{IG_USER_ID}/media"
    params = {
        "fields": "id,like_count,comments_count,timestamp,caption,media_type,media_url,thumbnail_url",
        "limit": limit,
        "access_token": TOKEN,
    }
    r = requests.get(url, params=params, timeout=30)
    if r.status_code == 200:
        return r.json().get("data", [])
    print(f"⚠️  Media fetch failed: {r.json().get('error', {}).get('message', r.text)}")
    return []


def score_post(post: dict) -> float:
    return post.get("like_count", 0) + post.get("comments_count", 0) * 2


def is_old_enough(timestamp_str: str) -> bool:
    try:
        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - ts
        return age >= timedelta(days=MIN_AGE_DAYS)
    except Exception:
        return False


def recycled_recently(post_id: str, state: dict) -> bool:
    recycled_at = state.get(post_id, {}).get("recycled_at")
    if not recycled_at:
        return False
    try:
        recycled_ts = datetime.fromisoformat(recycled_at)
        age = datetime.now(timezone.utc) - recycled_ts
        return age < timedelta(days=RECYCLE_COOLDOWN_DAYS)
    except Exception:
        return False


def repost(post: dict, username: str) -> str | None:
    """Repost using image_url via container + publish."""
    caption = (post.get("caption") or "").strip()
    new_caption = f"{caption}\n\n[Best of @{username}]" if caption else f"[Best of @{username}]"

    image_url = post.get("media_url") or post.get("thumbnail_url")
    if not image_url:
        print(f"  ✗ No media URL available for post {post['id']}")
        return None

    # Create container
    url = f"{GRAPH_BASE}/{IG_USER_ID}/media"
    params = {
        "image_url": image_url,
        "caption": new_caption,
        "access_token": TOKEN,
    }
    r = requests.post(url, data=params, timeout=30)
    if r.status_code != 200:
        print(f"  ✗ Container create failed: {r.json().get('error', {}).get('message', r.text)}")
        return None
    creation_id = r.json().get("id")

    time.sleep(5)

    # Publish
    pub_url = f"{GRAPH_BASE}/{IG_USER_ID}/media_publish"
    pub_params = {"creation_id": creation_id, "access_token": TOKEN}
    r2 = requests.post(pub_url, data=pub_params, timeout=30)
    if r2.status_code != 200:
        print(f"  ✗ Publish failed: {r2.json().get('error', {}).get('message', r2.text)}")
        return None
    return r2.json().get("id")


def main():
    print(f"[Content Recycler] Account: {ACCOUNT_NAME} | Username: @{USERNAME}")
    state = load_state()

    all_media = get_media(50)
    if not all_media:
        print("No media found.")
        return

    # Filter: old enough and not recycled recently
    eligible = [
        m for m in all_media
        if is_old_enough(m.get("timestamp", ""))
        and not recycled_recently(m["id"], state)
    ]

    if not eligible:
        print("No eligible posts to recycle (all too recent or recycled within 90 days).")
        return

    # Score and pick top 5, then pick the best not yet recycled
    top5 = sorted(eligible, key=score_post, reverse=True)[:5]
    best = top5[0]

    print(f"  Top post: {best['id']} | Score: {score_post(best):.0f} | Likes: {best.get('like_count',0)} | Posted: {best.get('timestamp','')}")
    print(f"  Caption preview: \"{(best.get('caption') or '')[:80]}\"")

    new_id = repost(best, USERNAME)
    if new_id:
        state[best["id"]] = {
            "recycled_at": datetime.now(timezone.utc).isoformat(),
            "new_post_id": new_id,
            "original_score": score_post(best),
        }
        save_state(state)
        print(f"  ✓ Recycled as new post: {new_id}")
    else:
        print("  ✗ Recycle failed.")
        sys.exit(1)

    print("[Content Recycler] Done.")


if __name__ == "__main__":
    main()
