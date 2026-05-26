"""
Master Agent — fetches real Graph API metrics, evolves strategy, generates content.
Runs before every post. Self-evolving: learns what works and doubles down on it.
"""
import json, os, requests
from datetime import datetime
from .config import ACCOUNT_NICHE, CONTENT_PILLARS, HASHTAG_POOLS
from .memory import load_memory, save_memory, load_posted, save_posted

GRAPH_BASE = "https://graph.facebook.com/v21.0"


def sync_metrics(ig_user_id: str, page_token: str):
    """Pull fresh likes/comments from Graph API and update posted_content.json."""
    posts = load_posted()
    if not posts:
        return
    try:
        r = requests.get(
            f"{GRAPH_BASE}/{ig_user_id}/media",
            params={"fields": "id,like_count,comments_count", "limit": 20, "access_token": page_token},
            timeout=20,
        )
        r.raise_for_status()
        live_map = {p["id"]: p for p in r.json().get("data", [])}
        for p in posts:
            pid = p.get("post_id", "")
            if pid in live_map:
                p["likes"]    = live_map[pid].get("like_count", 0)
                p["comments"] = live_map[pid].get("comments_count", 0)
                p["checked_at"] = datetime.utcnow().isoformat()
        save_posted(posts)
        print(f"  [MASTER] Synced metrics for {len(posts)} posts.")
    except Exception as e:
        print(f"  [MASTER] Metrics sync failed: {e}")


def maybe_evolve(client, force: bool = False) -> str:
    """Evolve strategy every 5 posts or when forced."""
    posts = load_posted()
    mem   = load_memory()
    if not force and len(posts) % 5 != 0:
        return mem.get("strategy_notes", "")
    if len(posts) < 3:
        return mem.get("strategy_notes", "")

    scored  = sorted(posts, key=lambda x: x.get("likes", 0) + x.get("comments", 0) * 3, reverse=True)
    top     = scored[:5]
    bottom  = scored[-3:] if len(scored) > 5 else []
    pillars = "\n".join(f"- {p}" for p in CONTENT_PILLARS)

    top_str    = "\n".join(f"- {p['topic']} | Likes:{p.get('likes',0)} Comments:{p.get('comments',0)}" for p in top)
    bottom_str = "\n".join(f"- {p['topic']} | Likes:{p.get('likes',0)} Comments:{p.get('comments',0)}" for p in bottom)

    resp = client.messages.create(
        model="llama-3.3-70b-versatile",
        max_tokens=500,
        system=(
            f"You are a growth strategist for bharat.vistas, an Indian travel photography Instagram.\n"
            f"Niche: {ACCOUNT_NICHE}\nContent pillars:\n{pillars}\n\n"
            "Based on real engagement data, write a precise 3-5 bullet strategy. "
            "Be specific: name content formats, hooks, topics that work best. "
            "Tell the content agent exactly what kind of post to make."
        ),
        messages=[{"role": "user", "content": (
            f"TOP performers:\n{top_str}\n\nLOW performers:\n{bottom_str}\n\n"
            f"Total posts so far: {len(posts)}\nWrite updated strategy:"
        )}]
    )

    strategy = resp.content[0].text.strip()
    mem["strategy_notes"] = strategy
    mem["last_evolved"]   = datetime.utcnow().isoformat()
    mem.setdefault("evolution_log", []).append({
        "date": datetime.utcnow().isoformat()[:10], "strategy": strategy
    })
    save_memory(mem)
    print(f"  [MASTER] Strategy evolved after {len(posts)} posts.")
    return strategy


def generate_content(client) -> dict:
    """Generate today's post — topic, caption, hashtags, image_prompt."""
    mem           = load_memory()
    strategy      = mem.get("strategy_notes", "")
    today         = datetime.utcnow().strftime("%B %d, %Y")
    recent_topics = [p.get("topic", "") for p in load_posted()[-10:]]

    resp = client.messages.create(
        model="llama-3.3-70b-versatile",
        max_tokens=1200,
        system=(
            f"You are the content brain for bharat.vistas — an Indian travel photography Instagram page.\n"
            f"Today is {today}. Niche: {ACCOUNT_NICHE}\n\n"
            "Generate ONE complete Instagram post. Rules:\n"
            "- Topic must feel current and relevant to Indian travel, photography, and culture world right now\n"
            "- Caption: 150-200 words. Punchy first line (hook). Build to a strong CTA. No hashtags. No filler.\n"
            "- Tone: passionate travel photographer — vivid, evocative, adventurous. Real, not corporate.\n"
            "- image_prompt: 2 sentences for FLUX AI image gen. Cinematic golden-hour Indian landscape photography aesthetic. No text in image.\n"
            "- hashtags: exactly 20 relevant tags as a JSON array of strings\n\n"
            "Return ONLY valid JSON: {topic, pillar, caption, image_prompt, hashtags}"
        ),
        messages=[{"role": "user", "content": (
            f"Strategy:\n{strategy}\n\n"
            f"Do NOT repeat these recent topics:\n" + "\n".join(f"- {t}" for t in recent_topics) + "\n\n"
            "Generate today's post JSON:"
        )}]
    )

    return _parse_json(resp.content[0].text.strip())


def _parse_json(text: str) -> dict:
    if "```" in text:
        for part in text.split("```"):
            part = part.strip().lstrip("json").strip()
            try:
                return json.loads(part)
            except Exception:
                pass
    try:
        return json.loads(text)
    except Exception:
        s = text.find("{"); e = text.rfind("}") + 1
        if s != -1:
            return json.loads(text[s:e])
    raise ValueError(f"Master agent returned invalid JSON: {text[:200]}")
