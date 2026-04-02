import json
import os
import random
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests


RSS_URL = "https://weebcentral.com/series/01J76XYDGDQERFSK333582BNBZ/rss"
STATE_FILE = "state.json"
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
GIPHY_API_KEY = os.getenv("GIPHY_API_KEY")

GIPHY_QUERIES = [
    "frieren beyond journey's end",
    "sousou no frieren",
    "frieren anime",
    "frieren gif",
    "fern frieren",
    "stark frieren",
]

MAX_SAVED_GIFS = 200


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


def get_used_gif_ids(state: dict) -> list[str]:
    used_ids = state.get("used_gif_ids", [])
    if isinstance(used_ids, list):
        return used_ids
    return []


def save_used_gif_id(state: dict, gif_id: str) -> None:
    used_ids = get_used_gif_ids(state)
    used_ids.append(gif_id)
    state["used_gif_ids"] = used_ids[-MAX_SAVED_GIFS:]


def search_giphy(query: str) -> list[dict]:
    if not GIPHY_API_KEY:
        raise ValueError("GIPHY_API_KEY não definida")

    response = requests.get(
        "https://api.giphy.com/v1/gifs/search",
        params={
            "api_key": GIPHY_API_KEY,
            "q": query,
            "limit": 20,
            "rating": "pg",
            "lang": "en",
        },
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    return data.get("data", [])


def deduplicate_gifs(results: list[dict]) -> list[dict]:
    seen = set()
    unique = []

    for gif in results:
        gif_id = gif.get("id")
        if not gif_id or gif_id in seen:
            continue
        seen.add(gif_id)
        unique.append(gif)

    return unique


def get_best_gif(gif: dict) -> tuple[str, str]:
    gif_id = gif.get("id", "")
    images = gif.get("images", {})

    gif_url = (
        images.get("original", {}).get("url")
        or images.get("downsized_large", {}).get("url")
        or images.get("fixed_height", {}).get("url")
        or ""
    )

    return gif_id, gif_url


def choose_frieren_gif(state: dict) -> str | None:
    used_ids = set(get_used_gif_ids(state))
    all_results = []

    for query in GIPHY_QUERIES:
        print(f"Buscando GIFs para: {query}")
        all_results.extend(search_giphy(query))

    unique_results = deduplicate_gifs(all_results)
    fresh_results = [gif for gif in unique_results if gif.get("id") not in used_ids]

    pool = fresh_results if fresh_results else unique_results
    if not pool:
        return None

    chosen_gif = random.choice(pool)
    gif_id, gif_url = get_best_gif(chosen_gif)

    if not gif_url:
        return None

    if gif_id:
        save_used_gif_id(state, gif_id)

    return gif_url


def send_discord_embed(
    description: str,
    color: int = 0x9B59B6,
    image_url: str | None = None,
) -> None:
    if not DISCORD_WEBHOOK_URL:
        raise ValueError("DISCORD_WEBHOOK_URL não definida")

    embed = {
        "description": description,
        "color": color,
    }

    if image_url:
        embed["image"] = {"url": image_url}

    payload = {
        "embeds": [embed]
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

    latest_title = latest.get("title", "Capítulo novo")
    latest_link = latest.get("link", "")
    latest_guid = latest.get("id") or latest.get("guid") or latest_link
    latest_date = parse_entry_date(latest)
    latest_chapter = extract_chapter_number(latest_title)
    chapter_text = latest_chapter if latest_chapter else latest_title

    state = load_state()
    last_guid = state.get("last_guid")

    gif_url = choose_frieren_gif(state)

    if last_guid != latest_guid:
        date_text = (
            latest_date.strftime("%d/%m/%Y")
            if latest_date
            else "data indisponível"
        )

        description = (
            f"**SAIU**\n\n"
            f"Capítulo {chapter_text}\n"
            f"Data: {date_text}\n"
            f"{latest_link}"
        )

        send_discord_embed(
            description=description,
            color=0x57F287,
            image_url=gif_url,
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
        f"**Não :(**\n\n"
        f"**O último capítulo foi o {chapter_text} e saiu {days_text}.**"
    )

    send_discord_embed(
        description=description,
        color=0x9B59B6,
        image_url=gif_url,
    )

    save_state(state)
    print("Nenhum capítulo novo. Mensagem de status enviada.")


if __name__ == "__main__":
    main()