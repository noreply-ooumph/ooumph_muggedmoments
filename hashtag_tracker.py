#!/usr/bin/env python3
"""Hashtag Tracker — finds recent posts for niche hashtags and leaves relevant comments."""

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

STATE_FILE = Path("hashtag_tracked.json")
MAX_COMMENTS = 3
COMMENT_DELAY = 60  # seconds
MAX_AGE_HOURS = 24
MAX_HASHTAGS_PER_WEEK = 15

ACCOUNT_HASHTAGS = {
    "thegurukul.online": ["gurukul", "ancientwisdom", "indianeducation", "vedic", "gurukulsystem"],
    "ooumph_official": ["web3india", "ooumphcoin", "cryptoindia", "blockchain", "defi"],
    "bharat.vistas": ["bharatvistas", "incredibleindia", "indiatravel", "travelphotography", "devbhoomi"],
    "muggedmoments": ["coffeetime", "aestheticcoffee", "muglife", "coffeelovers", "cozycoffee"],
}

COMMENT_SYSTEM = {
    "thegurukul.online": (
        "You are a warm, wise Indian educator. Write a short appreciative comment (max 1-2 sentences) "
        "for a post using education/wisdom hashtags. Be genuine and encouraging."
    ),
    "ooumph_official": (
        "You are an energetic Web3 enthusiast. Write a short comment (max 1-2 sentences) "
        "engaging with a crypto/blockchain post. Be positive and community-focused."
    ),
    "bharat.vistas": (
        "You are a passionate Indian travel photographer. Write a short evocative comment "
        "(max 1-2 sentences) for a travel/India post. Be genuine."
    ),
    "muggedmoments": (
        "You are a cozy coffee lover. Write a short warm comment (max 1-2 sentences) "
        "for a coffee-related post. Be friendly and relatable."
    ),
}

HASHTAGS = ACCOUNT_HASHTAGS.get(ACCOUNT_NAME, [])
SYSTEM_PROMPT = COMMENT_SYSTEM.get(ACCOUNT_NAME, "Write a short friendly comment. Max 2 sentences.")


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {"processed": [], "weekly_hashtags": {}}
    return {"processed": [], "weekly_hashtags": {}}


def save_state(data: dict):
    STATE_FILE.write_text(json.dumps(data, indent=2))


def get_week_key():
    now = datetime.now(timezone.utc)
    return f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"


def hashtags_used_this_week(state: dict) -> list:
    week = get_week_key()
    return state.get("weekly_hashtags", {}).get(week, [])


def record_hashtag_used(state: dict, hashtag: str):
    week = get_week_key()
    wh = state.setdefault("weekly_hashtags", {})
    if week not in wh:
        wh[week] = []
    if hashtag not in wh[week]:
        wh[week].append(hashtag)


def get_hashtag_id(hashtag: str) -> str | None:
    url = f"{GRAPH_BASE}/ig_hashtag_search"
    params = {"user_id": IG_USER_ID, "q": hashtag, "access_token": TOKEN}
    r = requests.get(url, params=params, timeout=30)
    if r.status_code == 200:
        data = r.json().get("data", [])
        return data[0]["id"] if data else None
    print(f"  ⚠️  Hashtag search failed for #{hashtag}: {r.json().get('error', {}).get('message', r.text)}")
    return None


def get_recent_media(hashtag_id: str) -> list:
    url = f"{GRAPH_BASE}/{hashtag_id}/recent_media"
    params = {
        "user_id": IG_USER_ID,
        "fields": "id,timestamp,media_type",
        "limit": 10,
        "access_token": TOKEN,
    }
    r = requests.get(url, params=params, timeout=30)
    if r.status_code == 200:
        return r.json().get("data", [])
    print(f"  ⚠️  Recent media fetch failed: {r.json().get('error', {}).get('message', r.text)}")
    return []


def is_too_old(timestamp_str: str) -> bool:
    try:
        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - ts
        return age > timedelta(hours=MAX_AGE_HOURS)
    except Exception:
        return False


def groq_comment(hashtag: str) -> str:
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Write a comment for a post using the hashtag #{hashtag}."},
        ],
        "max_tokens": 35,
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


def main():
    print(f"[Hashtag Tracker] Account: {ACCOUNT_NAME} | IG user: {IG_USER_ID}")
    if not HASHTAGS:
        print("No hashtags configured. Exiting.")
        return

    state = load_state()
    processed_ids = set(state.get("processed", []))
    used_this_week = hashtags_used_this_week(state)

    if len(used_this_week) >= MAX_HASHTAGS_PER_WEEK:
        print(f"⚠️  Weekly hashtag limit reached ({MAX_HASHTAGS_PER_WEEK}). Skipping.")
        return

    comments_posted = 0
    available_hashtags = [h for h in HASHTAGS if len(used_this_week) < MAX_HASHTAGS_PER_WEEK]

    for hashtag in available_hashtags:
        if comments_posted >= MAX_COMMENTS:
            break

        print(f"  Searching #{hashtag}...")
        hashtag_id = get_hashtag_id(hashtag)
        if not hashtag_id:
            continue

        record_hashtag_used(state, hashtag)
        used_this_week = hashtags_used_this_week(state)

        media_list = get_recent_media(hashtag_id)
        if not media_list:
            continue

        for media in media_list:
            if comments_posted >= MAX_COMMENTS:
                break
            media_id = media.get("id", "")
            if media_id in processed_ids:
                continue
            ts = media.get("timestamp", "")
            if is_too_old(ts):
                processed_ids.add(media_id)
                continue

            try:
                comment = groq_comment(hashtag)
                print(f"    Post {media_id} | Comment: \"{comment}\"")
                if post_comment(media_id, comment):
                    processed_ids.add(media_id)
                    comments_posted += 1
                    print(f"    ✓ Comment posted ({comments_posted}/{MAX_COMMENTS})")
                    if comments_posted < MAX_COMMENTS:
                        time.sleep(COMMENT_DELAY)
                else:
                    processed_ids.add(media_id)
            except Exception as e:
                print(f"    ✗ Error: {e}")
                processed_ids.add(media_id)

        time.sleep(5)  # delay between hashtags

    state["processed"] = list(processed_ids)
    save_state(state)
    print(f"[Hashtag Tracker] Done. Comments posted: {comments_posted}")


if __name__ == "__main__":
    main()
