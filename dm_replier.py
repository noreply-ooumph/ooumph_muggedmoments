#!/usr/bin/env python3
"""DM Auto-Replier — polls conversations and replies to unread DMs via Meta Graph API."""

import os, sys, json, time, random
from pathlib import Path
from dotenv import load_dotenv
import requests

load_dotenv()

GRAPH_BASE = "https://graph.facebook.com/v21.0"
TOKEN = os.environ["GRAPH_PAGE_TOKEN"]
IG_USER_ID = os.environ["GRAPH_IG_USER_ID"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
ACCOUNT_NAME = os.environ.get("ACCOUNT_NAME", "instagram")

STATE_FILE = Path("replied_dms.json")
MAX_REPLIES = 5

REPLY_SYSTEM = {
    "thegurukul.online": (
        "You are a warm, wise, educational assistant for an Indian gurukul account. "
        "Reply like a knowledgeable guru — concise, uplifting, and rooted in ancient wisdom."
    ),
    "ooumph_official": (
        "You are an energetic, Web3-native, crypto-passionate assistant. "
        "Reply with enthusiasm about blockchain, OoumphCoin, and the decentralized future. Keep it short."
    ),
    "bharat.vistas": (
        "You are a travel-inspired, culturally rich assistant for an Indian travel photography account. "
        "Reply with evocative, warm language about India's beauty and culture."
    ),
    "muggedmoments": (
        "You are a cozy, warm, coffee-passionate assistant. "
        "Reply like a friendly barista who loves aesthetic coffee culture and slow mornings."
    ),
}

SYSTEM_PROMPT = REPLY_SYSTEM.get(ACCOUNT_NAME, "You are a friendly Instagram assistant. Reply briefly and warmly.")


def load_replied():
    if STATE_FILE.exists():
        try:
            return set(json.loads(STATE_FILE.read_text()))
        except Exception:
            return set()
    return set()


def save_replied(ids: set):
    STATE_FILE.write_text(json.dumps(list(ids), indent=2))


def groq_reply(user_message: str) -> str:
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Someone sent this DM: \"{user_message}\"\nWrite a warm, brief reply (max 2 sentences)."},
        ],
        "max_tokens": 60,
        "temperature": 0.8,
    }
    resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def get_conversations():
    url = f"{GRAPH_BASE}/{IG_USER_ID}/conversations"
    params = {
        "fields": "messages{message,from,to,created_time,id}",
        "limit": 5,
        "access_token": TOKEN,
    }
    resp = requests.get(url, params=params, timeout=30)
    if resp.status_code == 200:
        return resp.json().get("data", [])
    err = resp.json().get("error", {})
    if "instagram_manage_messages" in err.get("message", "") or err.get("code") == 10:
        print("⚠️  Missing instagram_manage_messages permission — skipping DM replier.")
        sys.exit(0)
    print(f"⚠️  Could not fetch conversations: {err.get('message', resp.text)}")
    return []


def send_reply(message_id: str, reply_text: str) -> bool:
    url = f"{GRAPH_BASE}/{message_id}/replies"
    resp = requests.post(url, data={"message": reply_text, "access_token": TOKEN}, timeout=30)
    if resp.status_code == 200:
        return True
    print(f"  ✗ Reply failed: {resp.json().get('error', {}).get('message', resp.text)}")
    return False


def main():
    print(f"[DM Replier] Account: {ACCOUNT_NAME} | IG user: {IG_USER_ID}")
    replied = load_replied()
    conversations = get_conversations()
    if not conversations:
        print("No conversations found.")
        return

    replies_sent = 0
    for conv in conversations:
        if replies_sent >= MAX_REPLIES:
            break
        messages = conv.get("messages", {}).get("data", [])
        for msg in messages:
            if replies_sent >= MAX_REPLIES:
                break
            msg_id = msg.get("id", "")
            if msg_id in replied:
                continue
            from_user = msg.get("from", {})
            # Skip messages from self
            if str(from_user.get("id", "")) == str(IG_USER_ID):
                replied.add(msg_id)
                continue
            text = msg.get("message", "").strip()
            if not text:
                continue
            print(f"  → Replying to msg {msg_id} from {from_user.get('username', from_user.get('id'))}: \"{text[:60]}\"")
            try:
                reply = groq_reply(text)
                print(f"    Reply: \"{reply}\"")
                if send_reply(msg_id, reply):
                    replied.add(msg_id)
                    replies_sent += 1
                    print(f"    ✓ Sent ({replies_sent}/{MAX_REPLIES})")
                    time.sleep(random.uniform(3, 7))
            except Exception as e:
                print(f"    ✗ Error: {e}")
                replied.add(msg_id)  # Mark to avoid retry loops

    save_replied(replied)
    print(f"[DM Replier] Done. Replies sent: {replies_sent}")


if __name__ == "__main__":
    main()
