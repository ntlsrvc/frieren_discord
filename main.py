import json
import os
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests


RSS_URL = "https://weebcentral.com/series/01J76XYDGDQERFSK333582BNBZ/rss"
STATE_FILE = "state.json"
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)


def extract_chapter_number(title: str) -> str | None:
    match = re.search(r"Chapter\s+(\d+)", title, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def parse_entry_date(entry) -> datetime | None:
    pub_date = entry.get("published") or entry.get("pubDate")
    if not pub_date:
        return None

    try:
        parsed = parsedate_to_datetime(pub_date)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def days_since(date_value: datetime | None) -> int | None:
    if date_value is None:
        return None

    now = datetime.now(timezone.utc)
    delta = now - date_value
    return delta.days


def send_discord_embed(title: str, description: str, color: int = 0x9B59B6) -> None:
    if not DISCORD_WEBHOOK_URL:
        raise ValueError("DISCORD_WEBHOOK_URL não definida")

    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
            }
        ]
    }

    response = requests.post(
        DISCORD_WEBHOOK_URL,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()


def main() -> None:
    feed = feedparser.parse(RSS_URL)

    if not feed.entries:
        raise ValueError("O RSS não retornou capítulos.")

    latest = feed.entries[0]

    manga_title = feed.feed.get("title", "Mangá")
    latest_title = latest.get("title", "Capítulo novo")
    latest_link = latest.get("link", "")
    latest_guid = latest.get("id") or latest.get("guid") or latest_link
    latest_date = parse_entry_date(latest)
    latest_chapter = extract_chapter_number(latest_title)
    chapter_text = latest_chapter if latest_chapter else latest_title

    state = load_state()
    last_guid = state.get("last_guid")

    if last_guid != latest_guid:
        date_text = (
            latest_date.strftime("%d/%m/%Y %H:%M UTC")
            if latest_date
            else "data indisponível"
        )

        description = (
            f"**Capítulo {chapter_text}**\n"
            f"Publicado em: {date_text}\n"
            f"Link: {latest_link}"
        )

        send_discord_embed(
            title=f"Novo capítulo de {manga_title}",
            description=description,
            color=0x57F287,
        )

        state["last_guid"] = latest_guid
        state["last_title"] = latest_title
        state["last_link"] = latest_link
        state["last_pub_date"] = latest_date.isoformat() if latest_date else None
        save_state(state)
        print("Novo capítulo encontrado e notificação enviada.")
        return

    elapsed_days = days_since(latest_date)

    if elapsed_days is None:
        days_text = "há alguns dias"
    elif elapsed_days == 1:
        days_text = "há 1 dia"
    else:
        days_text = f"há {elapsed_days} dias"

    description = (
        "Não :(\n"
        f"O último capítulo foi o {chapter_text} e saiu {days_text}."
    )

    send_discord_embed(
        title="E Frieren saiu do hiato?",
        description=description,
        color=0x9B59B6,
    )

    print("Nenhum capítulo novo. Mensagem de status enviada.")


if __name__ == "__main__":
    main()