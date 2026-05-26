"""
Brain memory — stores performance, learns what works, evolves strategy.
"""
import json
from datetime import datetime
from .config import MEMORY_FILE, POSTED_FILE


def load_memory() -> dict:
    if MEMORY_FILE.exists():
        return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    return {
        "total_posts": 0,
        "total_comments_replied": 0,
        "top_performing_topics": [],
        "strategy_notes": "Post content that blends ancient Indian wisdom with modern education — motivational, insightful, visually compelling.",
        "evolution_log": [],
        "last_evolved": None,
    }

def save_memory(mem: dict):
    MEMORY_FILE.write_text(json.dumps(mem, indent=2, ensure_ascii=False), encoding="utf-8")

def load_posted() -> list:
    if POSTED_FILE.exists():
        return json.loads(POSTED_FILE.read_text(encoding="utf-8"))
    return []

def save_posted(posts: list):
    POSTED_FILE.write_text(json.dumps(posts, indent=2, ensure_ascii=False), encoding="utf-8")

def record_post(post_id: str, shortcode: str, topic: str, caption: str, hashtags: list):
    posts = load_posted()
    posts.append({
        "post_id": post_id, "shortcode": shortcode, "topic": topic,
        "caption": caption[:200], "hashtags": hashtags,
        "posted_at": datetime.now().isoformat(), "likes": 0, "comments": 0,
    })
    save_posted(posts)
    mem = load_memory()
    mem["total_posts"] += 1
    save_memory(mem)

def update_post_metrics(shortcode: str, likes: int, comments: int):
    posts = load_posted()
    for p in posts:
        if p["shortcode"] == shortcode:
            p["likes"] = likes
            p["comments"] = comments
            p["checked_at"] = datetime.now().isoformat()
    save_posted(posts)

def evolve_strategy(client) -> str:
    """Re-evaluate content strategy based on post performance."""
    posts = load_posted()
    mem   = load_memory()
    if len(posts) < 3:
        return mem["strategy_notes"]

    recent = sorted(posts, key=lambda x: x.get("likes", 0) + x.get("comments", 0) * 3, reverse=True)[:10]
    summary = "\n".join([
        f"- Topic: {p['topic']} | Likes: {p['likes']} | Comments: {p['comments']}"
        for p in recent
    ])

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        system=(
            "You are an Instagram growth strategist for thegurukul.online, an education and wisdom account. "
            "Analyze post performance and write an updated strategy in 3-5 bullet points. "
            "Focus on topics, formats, and hooks that drive most engagement."
        ),
        messages=[{"role": "user", "content": f"Recent performance:\n{summary}\n\nWrite updated strategy:"}]
    )
    new_strategy = resp.content[0].text.strip()
    mem["strategy_notes"] = new_strategy
    mem["last_evolved"] = datetime.now().isoformat()
    mem["evolution_log"].append({"date": datetime.now().isoformat()[:10], "strategy": new_strategy})
    save_memory(mem)
    print(f"[EVOLVER] Strategy updated:\n{new_strategy}\n")
    return new_strategy
