"""
SEO + AEO Optimizer — captions, hashtags, image prompts via Claude.
"""
import random
from .config import HASHTAG_POOLS, CONTENT_PILLARS, ACCOUNT_NICHE
from .memory import load_memory


def pick_hashtags(topic: str, count: int = 25) -> list:
    t = topic.lower()
    pool = []
    if any(w in t for w in ["gurukul","vedic","upanishad","ancient","wisdom","gita","mahab","ramay","sanskriti"]):
        pool += HASHTAG_POOLS.get("india", [])
    if any(w in t for w in ["study","learn","course","skill","exam","student","college","school"]):
        pool += HASHTAG_POOLS.get("education", [])
    if any(w in t for w in ["motivat","mindset","habit","discipline","success","goal","growth"]):
        pool += HASHTAG_POOLS.get("motivation", [])
    if any(w in t for w in ["youth","career","job","purpose","young","future"]):
        pool += HASHTAG_POOLS.get("youth", [])
    if any(w in t for w in ["philosoph","wisdom","conscious","soul","spirit","meaning","life"]):
        pool += HASHTAG_POOLS.get("wisdom", [])
    if any(w in t for w in ["ai","artificial","tech","digital","online","app","tool"]):
        pool += HASHTAG_POOLS.get("ai", [])
    pool += HASHTAG_POOLS.get("general", [])
    seen, out = set(), []
    for tag in pool:
        if tag not in seen:
            seen.add(tag); out.append(tag)
    random.shuffle(out)
    return out[:count]


def generate_seo_caption(client, topic: str, pillar: str) -> str:
    mem      = load_memory()
    strategy = mem.get("strategy_notes", "")

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=700,
        system=(
            "You are an expert Instagram SEO and AEO content writer for thegurukul.online, "
            f"an online education and ancient Indian wisdom account. Niche: {ACCOUNT_NICHE}\n\n"
            "SEO Rules: First line = powerful hook. Include 2-3 natural keyword phrases. Short paragraphs.\n\n"
            "AEO Rules: Include a direct factual/wisdom statement early. "
            "Structure: Hook → Wisdom/Insight → Practical takeaway → CTA.\n\n"
            "Tone: knowledgeable mentor — warm, grounded, inspiring. "
            "Format: 150-250 words. Tasteful emojis. End with 1 engaging question. NO hashtags."
        ),
        messages=[{"role": "user", "content": (
            f"Topic: {topic}\nPillar: {pillar}\nStrategy: {strategy}\n\nWrite the Instagram caption:"
        )}]
    )
    return resp.content[0].text.strip()


def generate_image_prompt(client, topic: str) -> str:
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        system="Write only a FLUX/Stable Diffusion image generation prompt. 2-3 sentences. No explanation.",
        messages=[{"role": "user", "content": (
            f"Topic: {topic}\n"
            "Style: cinematic, inspiring, warm golden light, ancient Indian aesthetic meets modern design, "
            "motivational, hyper-detailed, square 1:1 composition. No text in image."
        )}]
    )
    return resp.content[0].text.strip()
