"""
Image generation using HuggingFace free FLUX model.
Falls back to PIL-styled card if HF is unavailable.
"""
import time
import requests
from pathlib import Path
from .config import IMAGES_DIR


HF_API_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
HF_HEADERS = {"Content-Type": "application/json"}  # no token needed for public models


def generate_image_hf(prompt: str) -> Path:
    """Try HuggingFace FLUX first; fall back to PIL card on any error."""
    print(f"  Generating image via HuggingFace FLUX...")
    try:
        payload = {"inputs": prompt, "parameters": {"width": 1024, "height": 1024}}
        resp = requests.post(HF_API_URL, headers=HF_HEADERS, json=payload, timeout=60)
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
            filename = IMAGES_DIR / f"post_{int(time.time())}.jpg"
            filename.write_bytes(resp.content)
            print(f"  HF image saved: {filename}")
            return filename
        elif resp.status_code == 503:
            print(f"  HF model loading, retrying once...")
            time.sleep(20)
            resp = requests.post(HF_API_URL, headers=HF_HEADERS, json=payload, timeout=90)
            if resp.status_code == 200 and resp.headers.get("content-type","").startswith("image"):
                filename = IMAGES_DIR / f"post_{int(time.time())}.jpg"
                filename.write_bytes(resp.content)
                return filename
    except Exception as e:
        print(f"  HF unavailable ({type(e).__name__}), using PIL card.")

    return generate_image_pil(prompt)


def generate_image_pil(prompt: str) -> Path:
    """Generate a warm golden-style text card using PIL."""
    try:
        from PIL import Image, ImageDraw
        import textwrap, math

        W, H = 1080, 1080
        img  = Image.new("RGB", (W, H), (20, 12, 4))
        draw = ImageDraw.Draw(img)

        # Warm golden gradient
        for y in range(H):
            t = y / H
            r = int(20 + 80  * math.sin(t * math.pi))
            g = int(12 + 50  * math.sin(t * math.pi))
            b = int(4  + 20  * math.sin(t * math.pi))
            draw.line([(0, y), (W, y)], fill=(r, g, b))

        # Decorative border
        for offset, color in [(30,(160,120,40)),(36,(120,90,25)),(42,(80,60,15))]:
            draw.rectangle([offset, offset, W-offset, H-offset], outline=color, width=1)

        # Topic text
        words   = prompt.replace("cinematic","").replace("inspiring","").strip()
        wrapped = textwrap.wrap(words[:120], width=18)
        y_pos   = H//2 - len(wrapped)*45
        for line in wrapped[:5]:
            draw.text((W//2+2, y_pos+2), line.upper(), fill=(40,25,5), anchor="mm")
            draw.text((W//2, y_pos), line.upper(), fill=(255, 220, 120), anchor="mm")
            y_pos += 90

        # Divider
        draw.line([(W//2-120, H-140), (W//2+120, H-140)], fill=(180, 140, 60), width=1)

        # Brand name
        draw.text((W//2, H-100), "thegurukul.online", fill=(220, 180, 80), anchor="mm")
        draw.text((W//2, H-68),  "Wisdom · Learning · Growth", fill=(140, 110, 40), anchor="mm")

        filename = IMAGES_DIR / f"post_{int(time.time())}.jpg"
        img.save(filename, "JPEG", quality=95)
        print(f"  PIL card saved: {filename}")
        return filename

    except ImportError:
        import subprocess, sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "-q"])
        return generate_image_pil(prompt)
