#!/usr/bin/env python3
"""Story Auto-Poster — generates a tip/quote, creates an image, and posts as an IG Story."""

import os, sys, json, time, random, base64
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import requests
from dotenv import load_dotenv

load_dotenv()

GRAPH_BASE = "https://graph.facebook.com/v21.0"
TOKEN = os.environ["GRAPH_PAGE_TOKEN"]
IG_USER_ID = os.environ["GRAPH_IG_USER_ID"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GH_PAT = os.environ["GH_PAT"]
ACCOUNT_NAME = os.environ.get("ACCOUNT_NAME", "instagram")
REPO_OWNER = os.environ.get("REPO_OWNER", "noreply-ooumph")
REPO_NAME = os.environ.get("REPO_NAME", "")
GITHUB_REF = os.environ.get("GITHUB_REF_NAME", "main")

STATE_FILE = Path("posted_stories.json")
IMAGE_PATH = Path("generated_images/pending_story.jpg")

NICHE_PROMPTS = {
    "thegurukul.online": (
        "Write a single short inspirational tip or quote about Indian ancient wisdom, "
        "gurukul education, or Vedic knowledge. Max 2 sentences. No hashtags."
    ),
    "ooumph_official": (
        "Write a single short energetic tip or quote about Web3, OoumphCoin, blockchain, or crypto. "
        "Max 2 sentences. No hashtags."
    ),
    "bharat.vistas": (
        "Write a single evocative short caption about Indian travel, culture, or landscape photography. "
        "Max 2 sentences. No hashtags."
    ),
    "muggedmoments": (
        "Write a single cozy, aesthetic short quote about coffee, slow mornings, or café culture. "
        "Max 2 sentences. No hashtags."
    ),
}

IMAGE_STYLE = {
    "thegurukul.online": "ancient Indian gurukul forest ashram, golden sunrise, Vedic wisdom, spiritual atmosphere, cinematic",
    "ooumph_official": "futuristic Web3 blockchain digital art, glowing crypto coins, neon blue purple, tech aesthetic",
    "bharat.vistas": "breathtaking Indian landscape travel photography, vibrant colors, golden hour, majestic mountains or temples",
    "muggedmoments": "cozy aesthetic coffee shop, latte art, warm light, minimalist, Instagram aesthetic, morning vibes",
}

NICHE_PROMPT = NICHE_PROMPTS.get(ACCOUNT_NAME, "Write a short inspirational quote. Max 2 sentences.")
IMG_STYLE = IMAGE_STYLE.get(ACCOUNT_NAME, "beautiful aesthetic Instagram story background")


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return []
    return []


def save_state(data):
    STATE_FILE.write_text(json.dumps(data, indent=2))


def already_posted_today(state):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return any(entry.get("date") == today for entry in state)


def groq_generate_text(prompt: str) -> str:
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 100,
        "temperature": 0.9,
    }
    resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def generate_image(style_prompt: str) -> bytes:
    seed = random.randint(1, 99999)
    encoded = quote(f"{style_prompt}, vertical 9:16 story format, no text overlay")
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&nologo=true&seed={seed}"
    print(f"  Generating image from Pollinations.ai (seed={seed})...")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    return resp.content


def commit_image_to_github(image_bytes: bytes) -> str:
    """Commit the image to GitHub and return the raw URL."""
    image_path_str = str(IMAGE_PATH).replace("\\", "/")
    api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{image_path_str}"
    headers = {"Authorization": f"token {GH_PAT}", "Accept": "application/vnd.github.v3+json"}

    sha = None
    r = requests.get(api_url, headers=headers, timeout=30)
    if r.status_code == 200:
        sha = r.json().get("sha")

    encoded = base64.b64encode(image_bytes).decode()
    payload = {
        "message": f"bot: add story image {datetime.now(timezone.utc).strftime('%Y-%m-%d')} [skip ci]",
        "content": encoded,
        "branch": GITHUB_REF,
    }
    if sha:
        payload["sha"] = sha

    r2 = requests.put(api_url, headers=headers, json=payload, timeout=60)
    r2.raise_for_status()
    raw_url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{GITHUB_REF}/{image_path_str}"
    print(f"  ✓ Image committed. Raw URL: {raw_url}")
    return raw_url


def post_story(image_url: str) -> str | None:
    """Create IG media container for story."""
    url = f"{GRAPH_BASE}/{IG_USER_ID}/media"
    params = {
        "media_type": "STORIES",
        "image_url": image_url,
        "access_token": TOKEN,
    }
    r = requests.post(url, data=params, timeout=30)
    if r.status_code != 200:
        print(f"  ✗ Media create failed: {r.json().get('error', {}).get('message', r.text)}")
        return None
    return r.json().get("id")


def publish_story(creation_id: str) -> str | None:
    url = f"{GRAPH_BASE}/{IG_USER_ID}/media_publish"
    params = {"creation_id": creation_id, "access_token": TOKEN}
    r = requests.post(url, data=params, timeout=30)
    if r.status_code != 200:
        print(f"  ✗ Publish failed: {r.json().get('error', {}).get('message', r.text)}")
        return None
    return r.json().get("id")


def main():
    print(f"[Story Poster] Account: {ACCOUNT_NAME} | Repo: {REPO_NAME}")
    state = load_state()

    if already_posted_today(state):
        print("✓ Already posted a story today. Skipping.")
        return

    print("  Generating story text...")
    try:
        text = groq_generate_text(NICHE_PROMPT)
        print(f"  Text: \"{text}\"")
    except Exception as e:
        print(f"✗ Groq error: {e}")
        sys.exit(1)

    try:
        image_bytes = generate_image(IMG_STYLE)
        IMAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        IMAGE_PATH.write_bytes(image_bytes)
        print(f"  ✓ Image saved locally ({len(image_bytes)} bytes)")
    except Exception as e:
        print(f"✗ Image generation error: {e}")
        sys.exit(1)

    try:
        raw_url = commit_image_to_github(image_bytes)
    except Exception as e:
        print(f"✗ GitHub commit error: {e}")
        sys.exit(1)

    time.sleep(5)  # Let GitHub CDN propagate

    try:
        creation_id = post_story(raw_url)
        if not creation_id:
            sys.exit(1)
        print(f"  ✓ Container created: {creation_id}")

        time.sleep(3)
        media_id = publish_story(creation_id)
        if not media_id:
            sys.exit(1)
        print(f"  ✓ Story published: {media_id}")
    except Exception as e:
        print(f"✗ Posting error: {e}")
        sys.exit(1)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state.append({"date": today, "media_id": media_id, "text": text})
    save_state(state)
    print(f"[Story Poster] Done. Story posted for {today}.")


if __name__ == "__main__":
    main()
