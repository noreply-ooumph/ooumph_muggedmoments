"""
Central config for bharat.vistas Instagram Brain
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

ACCOUNT_USERNAME = "bharat.vistas"
ACCOUNT_USER_ID  = 59542557883
ACCOUNT_NICHE    = "Indian travel photography, landscapes, heritage sites, nature, culture, and the beauty of Bharat"

POSTING_HOURS    = [9, 13, 18, 21]
POSTS_PER_DAY    = 1

REPLY_CHECK_INTERVAL = 300
REPLY_SLEEP_MIN      = 5
REPLY_SLEEP_MAX      = 15

EVOLUTION_AFTER_POSTS = 5

BASE_DIR      = Path(__file__).parent.parent
MEMORY_FILE   = BASE_DIR / "brain_memory.json"
POSTED_FILE   = BASE_DIR / "posted_content.json"
REPLIED_FILE  = BASE_DIR / "replied_comments.json"
IMAGES_DIR    = BASE_DIR / "generated_images"
IMAGES_DIR.mkdir(exist_ok=True)

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GROQ_KEY      = os.environ.get("GROQ_API_KEY", "")

CONTENT_PILLARS = [
    "Iconic Indian heritage sites and their untold stories",
    "Hidden gems — offbeat travel destinations across Bharat",
    "Indian landscapes — mountains, deserts, backwaters, forests",
    "Cultural festivals and traditions captured through the lens",
    "Street photography — colours and life of Indian cities",
    "Spiritual India — temples, ghats, and sacred places",
    "Wildlife and nature photography across Indian reserves",
    "Food and local cuisine from different states of India",
    "Travel tips and guides for exploring India",
    "Sunrise and sunset vistas from across the subcontinent",
]

HASHTAG_POOLS = {
    "travel":     ["#indiatravel", "#incredibleindia", "#bharatdarshan", "#travelindia", "#exploreindiaIG", "#indiatravelgram", "#wanderlust", "#travelphotography"],
    "heritage":   ["#heritageIndia", "#indiaheritage", "#historicalplaces", "#ancientindia", "#UNESCO", "#fortsofindia", "#templesofIndia"],
    "nature":     ["#naturephotography", "#landscapephotography", "#indiawildlife", "#indialandscape", "#mountains", "#himalayas", "#westernghats"],
    "culture":    ["#indianculture", "#festivalsofIndia", "#colorsofindia", "#streetphotography", "#indiaclicks", "#indiapictures"],
    "photography":["#photography", "#photooftheday", "#naturephoto", "#travelphotographer", "#goldenhour", "#shotoniphone", "#canon"],
    "general":    ["#reels", "#explore", "#viral", "#trending", "#instagram", "#fyp", "#instagood"],
}
