import random

import httpx
from bs4 import BeautifulSoup

ANKI_URL = "http://localhost:8765"


def anki(action, **params):
    r = httpx.post(ANKI_URL, json={"action": action, "version": 6, "params": params})
    return r.json()["result"]


# Cards due today or overdue in a specific deck
def get_due_cards(deck: str, limit: int) -> list[int]:
    query = f'deck:"{deck}" (is:due OR is:learn)'
    ids = anki("findCards", query=query)
    return ids[:limit]


def get_cards(deck: str, limit: int) -> list[int]:
    query = f'deck:"{deck} prop:ease<2.0"'
    ids = anki("findCards", query=query)
    return ids[:limit]


# Young cards (interval < 21 days) — great for grinding
def get_young_cards(deck: str, limit: int) -> list[int]:
    query = f'deck:"{deck}" prop:ivl<21 is:review'
    ids = anki("findCards", query=query)
    return ids[:limit]


# All due across multiple decks
def get_grindable_cards(decks: list[str], n_per_deck: int) -> list[int]:
    all_ids = []
    for deck in decks:
        ids = get_problematic(deck, n_per_deck)
        all_ids.extend(ids)

    return all_ids


# Tier 1: chronic failures (most worth grinding)
TIER1 = 'deck:"{deck}" prop:ivl>21 prop:lapses>3 prop:ease<2.1'

# Tier 2: fragile mature cards
TIER2 = 'deck:"{deck}" prop:ivl>21 prop:lapses>1 prop:ease<2.0'

# Tier 3: Anki-flagged leeches regardless of interval
TIER3 = 'deck:"{deck}" tag:leech'


def get_problematic(deck: str, limit: int) -> list[int]:
    for query_tmpl in [TIER1, TIER2, TIER3]:
        ids = anki("findCards", query=query_tmpl.format(deck=deck))
        if len(ids) >= limit:
            return ids[:limit]
    # fallback: union all tiers
    seen = set()
    result = []
    for tmpl in [TIER1, TIER2, TIER3]:
        for id_ in anki("findCards", query=tmpl.format(deck=deck)):
            if id_ not in seen:
                seen.add(id_)
                result.append(id_)
    return result[:limit]


def get_weighted_sample(decks: list[str], total: int) -> list[int]:
    # Get all due cards per deck
    per_deck = {d: anki("findCards", query=f'deck:"{d}" is:due') for d in decks}

    # Weight by number of due cards (more due = more samples)
    total_due = sum(len(v) for v in per_deck.values())
    result = []
    for deck, ids in per_deck.items():
        if not ids or total_due == 0:
            continue
        weight = len(ids) / total_due
        n = max(1, round(total * weight))
        result.extend(random.sample(ids, min(n, len(ids))))

    return result[:total]


def get_cards_info(card_ids: list[int]) -> list[dict]:
    return anki("cardsInfo", cards=card_ids)


def badness_score(card: dict) -> float:
    ease = card["factor"] / 1000
    lapses = card["lapses"]
    interval = card["interval"]

    ease_penalty = max(0, 2.5 - ease) * 3  # how far below default
    lapse_penalty = min(lapses, 10) * 0.5  # capped so one leech doesn't dominate
    interval_risk = min(interval / 30, 5) * 0.3  # longer interval = more at stake

    return ease_penalty + lapse_penalty + interval_risk


def main():
    PER_DECK = 200

    # Each card has: .fields, .deckName, .interval, .due, .factor, .note, etc.
    decks = [
        "🥝🐌💎눈_눈Mining(thy oldies)",
        "_",
        "🐢鼈とオポッサムと偽袋鼯鼠🐿️",
    ]
    cards = get_cards_info(get_grindable_cards(decks, n_per_deck=PER_DECK))

    # TOTAL = 200
    # cards = get_cards_info(get_weighted_sample(decks, TOTAL))

    possible_fields_to_go_through = [
        "Entry",
        "Kanji",
        "front",
        "Expression",
        "wordDictionaryForm",
    ]

    cards.sort(key=badness_score, reverse=True)
    words = []

    for card in cards:
        field_name = None
        for field in possible_fields_to_go_through:
            if field in card["fields"]:
                field_name = field
        if field_name is None:
            continue

        word = card["fields"][field_name]["value"]
        # reading = card["fields"].get("Reading", {}).get("value", "")
        # print(f"{word} ({reading}) — interval: {card['interval']}d")
        word = BeautifulSoup(word, "html.parser").text.strip()
        print(f"{word} ~ interval: {card['interval']}d")

        if word:
            words.append(word)

    with open("words.txt", "a") as f:
        f.write("\n".join(words) + "\n")


if __name__ == "__main__":
    main()
