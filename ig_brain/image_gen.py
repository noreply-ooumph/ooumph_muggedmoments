"""
Image generation using Pollinations.ai (free, no API key, works from GitHub Actions).
Falls back to PIL-styled card if unavailable.
"""
import time, random, requests
from pathlib import Path
from urllib.parse import quote
from .config import IMAGES_DIR

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}?width=1080&height=1080&nologo=true&seed={seed}&model=flux"


def generate_image_hf(prompt: str) -> Path:
    print(f"  Generating image via Pollinations.ai...")
    try:
        seed = random.randint(1, 99999)
        url  = POLLINATIONS_URL.format(prompt=quote(prompt), seed=seed)
        resp = requests.get(url, timeout=90)
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
            filename = IMAGES_DIR / f"post_{int(time.time())}.jpg"
            filename.write_bytes(resp.content)
            print(f"  Pollinations image saved: {filename}")
            return filename
        else:
            print(f"  Pollinations returned {resp.status_code}, using PIL card.")
    except Exception as e:
        print(f"  Pollinations unavailable ({type(e).__name__}), using PIL card.")
    return generate_image_pil(prompt)


def generate_image_pil(prompt: str) -> Path:
    try:
        from PIL import Image, ImageDraw
        import textwrap, math
        W, H    = 1080, 1080
        BG      = (20,12,4)
        MID     = (70,40,15)
        TEXT    = (230,180,120)
        SUB     = (200,150,90)
        BRAND   = "muggedmoments"
        TAGLINE = "Coffee - Aesthetic - Cozy Life"
        img  = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)
        for y in range(H):
            t = y / H
            r = int(BG[0] + (MID[0]-BG[0]) * math.sin(t * math.pi))
            g = int(BG[1] + (MID[1]-BG[1]) * math.sin(t * math.pi))
            b = int(BG[2] + (MID[2]-BG[2]) * math.sin(t * math.pi))
            draw.line([(0, y), (W, y)], fill=(r, g, b))
        for offset, alpha in [(30, 160), (36, 120), (42, 80)]:
            c = tuple(int(x * alpha // 255) for x in TEXT)
            draw.rectangle([offset, offset, W-offset, H-offset], outline=c, width=1)
        words   = prompt.replace("cinematic","").replace("inspiring","").strip()
        wrapped = textwrap.wrap(words[:120], width=18)
        y_pos   = H//2 - len(wrapped) * 45
        for line in wrapped[:5]:
            draw.text((W//2+2, y_pos+2), line.upper(), fill=tuple(x//5 for x in TEXT), anchor="mm")
            draw.text((W//2,   y_pos),   line.upper(), fill=TEXT, anchor="mm")
            y_pos += 90
        draw.line([(W//2-120, H-140), (W//2+120, H-140)], fill=SUB, width=1)
        draw.text((W//2, H-100), BRAND,   fill=TEXT, anchor="mm")
        draw.text((W//2, H-68),  TAGLINE, fill=SUB,  anchor="mm")
        filename = IMAGES_DIR / f"post_{int(time.time())}.jpg"
        img.save(filename, "JPEG", quality=95)
        print(f"  PIL card saved: {filename}")
        return filename
    except ImportError:
        import subprocess, sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "-q"])
        return generate_image_pil(prompt)
