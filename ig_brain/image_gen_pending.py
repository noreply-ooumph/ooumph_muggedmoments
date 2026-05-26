"""
Saves generated image as pending_post.jpg — fixed filename for GitHub CDN URL.
"""
from pathlib import Path
from .config import IMAGES_DIR
from .image_gen import generate_image_hf


def generate_pending_image(prompt: str) -> Path:
    """Generate image and save as pending_post.jpg (overwrites previous)."""
    tmp = generate_image_hf(prompt)
    pending = IMAGES_DIR / "pending_post.jpg"
    pending.write_bytes(tmp.read_bytes())
    print(f"  Image saved as pending_post.jpg")
    return pending
