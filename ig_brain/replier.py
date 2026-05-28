"""
Auto Comment Replier — monitors all posts, replies to every comment with Claude.
"""
import json, time, random, requests
from pathlib import Path
from .config import ACCOUNT_USERNAME, ACCOUNT_USER_ID, REPLY_SLEEP_MIN, REPLY_SLEEP_MAX, REPLIED_FILE

REPLY_SYSTEM = """You are the voice behind muggedmoments, an Instagram page dedicated to coffee culture, aesthetic mugs, cozy lifestyle, and beautiful everyday moments.

Reply to a comment on one of your posts. Rules:
- 1-2 sentences max
- Sound like a warm, cozy coffee enthusiast -- inviting and aesthetic
- If they asked about a recipe or brewing method, be helpful and share the cozy vibe
- If praise, be genuine and warm
- If a question about coffee, give a crisp, passionate answer
- Emojis are welcome -- keep it warm and cozy
- Never start with "Thanks for commenting!" or "Glad you liked it!"
- Vary sentence openers -- don't always start with "We" or "I"
"""


def load_replied() -> set:
    if REPLIED_FILE.exists():
        return set(json.loads(REPLIED_FILE.read_text(encoding="utf-8")))
    return set()

def save_replied(ids: set):
    REPLIED_FILE.write_text(json.dumps(list(ids), indent=2), encoding="utf-8")

def load_web_session() -> requests.Session:
    settings = json.loads((Path(__file__).parent.parent / "ig_settings.json").read_text(encoding="utf-8"))
    cookies  = settings.get("cookies", {})
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "X-CSRFToken": cookies.get("csrftoken", ""),
        "X-Instagram-AJAX": "1",
        "Referer": f"https://www.instagram.com/{ACCOUNT_USERNAME}/",
        "Origin": "https://www.instagram.com",
        "Accept": "application/json",
    })
    for k, v in cookies.items():
        s.cookies.set(k, v, domain=".instagram.com")
    return s

def fetch_posts(session: requests.Session = None) -> list:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "x-ig-app-id": "936619743392459",
        "Accept": "application/json",
    }
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={ACCOUNT_USERNAME}"
    if session:
        r = session.get(url, headers={**session.headers, **headers}, timeout=15)
    else:
        r = requests.get(url, headers=headers, timeout=15)
    if r.status_code != 200 or not r.content:
        raise ValueError(f"fetch_posts failed: status={r.status_code} len={len(r.content)}")
    data  = r.json()
    edges = data["data"]["user"]["edge_owner_to_timeline_media"]["edges"]
    return [
        {
            "id":      e["node"]["id"],
            "code":    e["node"]["shortcode"],
            "caption": (e["node"].get("edge_media_to_caption", {}).get("edges") or [{}])[0].get("node", {}).get("text", ""),
        }
        for e in edges
    ]

def _filter_comments(raw: list) -> list:
    result = []
    for c in raw:
        uid  = str(c.get("user_id", ""))
        text = c.get("text", "").strip()
        if uid == str(ACCOUNT_USER_ID):
            continue
        if text.lower().startswith(f"@{ACCOUNT_USERNAME.lower()}"):
            continue
        if c.get("already_replied"):
            continue
        result.append(c)
    return result

def _parse_v1_comments(data: dict) -> list:
    out = []
    for c in data.get("comments", []):
        uid = str((c.get("user") or {}).get("pk", ""))
        thread = c.get("child_comment_preview", {}).get("child_comments", [])
        already = any(str((t.get("user") or {}).get("pk", "")) == str(ACCOUNT_USER_ID) for t in thread)
        out.append({
            "id":       str(c.get("pk", "")),
            "text":     c.get("text", "").strip(),
            "username": (c.get("user") or {}).get("username", ""),
            "user_id":  uid,
            "already_replied": already,
        })
    return _filter_comments(out)

def _parse_graphql_comments(data: dict) -> list:
    edges = (data.get("data", {})
                 .get("shortcode_media", {})
                 .get("edge_media_to_parent_comment", {})
                 .get("edges", []))
    out = []
    for e in edges:
        node  = e.get("node", {})
        owner = node.get("owner", {})
        uid   = str(owner.get("id", ""))
        threaded = (node.get("edge_threaded_comments", {}).get("edges") or [])
        already  = any(
            str(rep.get("node", {}).get("owner", {}).get("id", "")) == str(ACCOUNT_USER_ID)
            for rep in threaded
        )
        out.append({
            "id":       str(node.get("id", "")),
            "text":     node.get("text", "").strip(),
            "username": owner.get("username", ""),
            "user_id":  uid,
            "already_replied": already,
        })
    return _filter_comments(out)

def fetch_comments(post_code: str, session: requests.Session, post_id: str = "") -> list:
    """Try v1 API first (more reliable on cloud IPs), fallback to GraphQL. Logs all errors."""
    # --- v1 API ---
    if post_id:
        try:
            r = session.get(
                f"https://www.instagram.com/api/v1/media/{post_id}/comments/",
                headers={**session.headers, "x-ig-app-id": "936619743392459"},
                timeout=15,
                allow_redirects=False,
            )
            print(f"    v1 status={r.status_code}", end="")
            if r.status_code == 200:
                comments = _parse_v1_comments(r.json())
                print(f" -> {len(comments)} comments")
                return comments
            elif r.status_code in (301, 302):
                loc = r.headers.get("Location", "")
                print(f" -> CHECKPOINT redirect: {loc[:80]}")
            else:
                try:
                    msg = r.json().get("message", r.text[:80])
                except Exception:
                    msg = r.text[:80]
                print(f" -> error: {msg}")
        except Exception as ex:
            print(f"    v1 exception: {ex}")

    # --- GraphQL fallback ---
    try:
        import urllib.parse
        variables = json.dumps({"shortcode": post_code, "first": 50})
        url = (
            "https://www.instagram.com/graphql/query/"
            "?query_hash=bc3296d1ce80a24b1b6e40b1e72903f5"
            f"&variables={urllib.parse.quote(variables)}"
        )
        r = session.get(url, timeout=15, allow_redirects=False)
        print(f"    graphql status={r.status_code}", end="")
        if r.status_code == 200:
            comments = _parse_graphql_comments(r.json())
            print(f" -> {len(comments)} comments")
            return comments
        else:
            try:
                msg = r.json().get("message", r.text[:80])
            except Exception:
                msg = r.text[:80]
            print(f" -> error: {msg}")
            return []
    except Exception as ex:
        print(f"    graphql exception: {ex}")
        return []

def generate_reply(client, comment: str, caption_hint: str) -> str:
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        system=REPLY_SYSTEM,
        messages=[{"role": "user", "content": f"Post topic: {caption_hint[:80]}\nComment: {comment}\n\nReply:"}]
    )
    return resp.content[0].text.strip().strip('"').strip("'")

def post_reply(session: requests.Session, post_id: str, comment_id: str, text: str) -> bool:
    r = session.post(
        f"https://www.instagram.com/api/v1/web/comments/{post_id}/add/",
        data={"comment_text": text, "replied_to_comment_id": comment_id},
        headers={**session.headers, "Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    return r.status_code in (200, 201)
