#!/usr/bin/env python3
"""Mention Monitor — finds posts where account is tagged and leaves warm comments."""

import os, sys, json, time, random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
import requests

load_dotenv()

GRAPH_BASE = "https://graph.facebook.com/v21.0"
TOKEN = os.environ["GRAPH_PAGE_TOKEN"]
IG_USER_ID = os.environ["GRAPH_IG_USER_ID"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
ACCOUNT_NAME = os.environ.get("ACCOUNT_NAME", "instagram")

STATE_FILE = Path("processed_mentions.json")
MAX_COMMENTS = 3
COMMENT_DELAY = 30  # seconds between comments
MAX_AGE_HOURS = 48

COMMENT_SYSTEM = {
    "thegurukul.online": (
        "You are a warm, wise Indian educator. Write a short appreciative comment (max 2 sentences) "
        "for a post that tagged our gurukul account. Be genuine and encouraging."
    ),
    "ooumph_official": (
        "You are an energetic Web3 enthusiast. Write a short enthusiastic comment (max 2 sentences) "
        "for a post that mentioned our crypto/Web3 account. Be positive and community-focused."
    ),
    "bharat.vistas": (
        "You are a passionate travel photographer. Write a short warm comment (max 2 sentences) "
        "appreciating a post that tagged our travel photography account. Be evocative and genuine."
    ),
    "muggedmoments": (
        "You are a cozy coffee lover. Write a short warm comment (max 2 sentences) "
        "for a post that tagged our coffee account. Be friendly and coffee-passionate."
    ),
}

SYSTEM_PROMPT = COMMENT_SYSTEM.get(ACCOUNT_NAME, "Write a short warm comment. Max 2 sentences.")


def load_state():
    if STATE_FILE.exists():
        try:
            return set(json.loads(STATE_FILE.read_text()))
        except Exception:
            return set()
    return set()


def save_state(ids: set):
    STATE_FILE.write_text(json.dumps(list(ids), indent=2))


def get_mentions():
    url = f"{GRAPH_BASE}/{IG_USER_ID}/tags"
    params = {
        "fields": "id,caption,timestamp,username",
        "access_token": TOKEN,
        "limit": 20,
    }
    r = requests.get(url, params=params, timeout=30)
    if r.status_code == 200:
        return r.json().get("data", [])
    print(f"⚠️  Could not fetch mentions: {r.json().get('error', {}).get('message', r.text)}")
    return []


def groq_comment(caption: str) -> str:
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    context = f"Post caption: \"{caption[:200]}\"" if caption else "No caption available."
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{context}\nWrite a warm, brief comment for this post."},
        ],
        "max_tokens": 40,
        "temperature": 0.85,
    }
    resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def post_comment(media_id: str, comment: str) -> bool:
    url = f"{GRAPH_BASE}/{media_id}/comments"
    r = requests.post(url, data={"message": comment, "access_token": TOKEN}, timeout=30)
    if r.status_code == 200:
        return True
    print(f"  ✗ Comment failed: {r.json().get('error', {}).get('message', r.text)}")
    return False


def is_too_old(timestamp_str: str) -> bool:
    try:
        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - ts
        return age > timedelta(hours=MAX_AGE_HOURS)
    except Exception:
        return False


def main():
    print(f"[Mention Monitor] Account: {ACCOUNT_NAME} | IG user: {IG_USER_ID}")
    processed = load_state()
    mentions = get_mentions()

    if not mentions:
        print("No mentions found.")
        return

    comments_posted = 0
    for mention in mentions:
        if comments_posted >= MAX_COMMENTS:
            break
        media_id = mention.get("id", "")
        if media_id in processed:
            continue
        timestamp = mention.get("timestamp", "")
        if is_too_old(timestamp):
            print(f"  Skipping old mention {media_id} ({timestamp})")
            processed.add(media_id)
            continue

        caption = mention.get("caption", "")
        username = mention.get("username", "unknown")
        print(f"  → New mention from @{username} (media: {media_id})")

        try:
            comment = groq_comment(caption)
            print(f"    Comment: \"{comment}\"")
            if post_comment(media_id, comment):
                processed.add(media_id)
                comments_posted += 1
                print(f"    ✓ Comment posted ({comments_posted}/{MAX_COMMENTS})")
                if comments_posted < MAX_COMMENTS:
                    time.sleep(COMMENT_DELAY)
            else:
                processed.add(media_id)
        except Exception as e:
            print(f"    ✗ Error: {e}")
            processed.add(media_id)

    save_state(processed)
    print(f"[Mention Monitor] Done. Comments posted: {comments_posted}")


if __name__ == "__main__":
    main()
