"""
Auto Poster — generates image + SEO caption, posts to Instagram via instagrapi.
"""
import json, os
from pathlib import Path
from instagrapi import Client
from .config import ACCOUNT_USERNAME, IMAGES_DIR
from .seo import pick_hashtags, generate_seo_caption, generate_image_prompt
from .image_gen import generate_image_hf
from .memory import record_post, load_posted, evolve_strategy
from .config import EVOLUTION_AFTER_POSTS


def get_client() -> Client:
    import sys
    from instagrapi.exceptions import LoginRequired, ChallengeRequired
    cl = Client()
    cl.delay_range = [1, 3]
    settings_path = Path(__file__).parent.parent / "ig_settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    if "_instagrapi" in settings:
        cl.set_settings(settings["_instagrapi"])
        print(f"  Session loaded for user_id={settings.get('user_id', '?')}")
        try:
            info = cl.account_info()
            print(f"  Session valid — @{info.username}")
        except (LoginRequired, ChallengeRequired) as e:
            print(f"  Session EXPIRED: {e}")
            print("  --> login.yml will be triggered by poster.yml on exit code 2")
            sys.exit(2)
        except Exception as e:
            err_str = str(e)
            if "Challenge" in err_str or "challenge" in err_str or "STEP_NAME" in err_str:
                print(f"  Session challenged — need fresh login: {err_str[:120]}")
                sys.exit(2)
            print(f"  Session validation warning: {e} — continuing anyway")
    else:
        cl.login(
            os.environ.get("IG_USERNAME", ACCOUNT_USERNAME),
            os.environ.get("IG_PASSWORD", ""),
        )
    return cl


def run_poster(client, topic_data: dict):
    topic  = topic_data.get("topic", "")
    pillar = topic_data.get("pillar", "")
    print(f"\n[POSTER] Topic: {topic}")

    print("  Generating SEO/AEO caption with Claude...")
    caption  = generate_seo_caption(client, topic, pillar)
    hashtags = pick_hashtags(topic)
    full_caption = caption + "\n\n" + " ".join(hashtags)
    print(f"  Caption ready ({len(caption)} chars), {len(hashtags)} hashtags.")

    print("  Generating image...")
    img_prompt = generate_image_prompt(client, topic)
    image_path = generate_image_hf(img_prompt)

    print("  Posting to Instagram via instagrapi...")
    cl = get_client()
    media = cl.photo_upload(str(image_path), caption=full_caption)
    shortcode = media.code
    post_id   = str(media.pk)
    print(f"  Posted! https://www.instagram.com/p/{shortcode}/")

    # Save refreshed session tokens
    try:
        updated = {"_instagrapi": cl.get_settings(), "user_id": str(cl.user_id)}
        (Path(__file__).parent.parent / "ig_settings.json").write_text(json.dumps(updated, indent=2))
    except Exception:
        pass

    record_post(post_id, shortcode, topic, caption, hashtags)
    if len(load_posted()) % EVOLUTION_AFTER_POSTS == 0:
        print("  Evolving content strategy...")
        evolve_strategy(client)

    return shortcode
