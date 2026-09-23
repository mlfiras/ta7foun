"""
Vérifie la disponibilité des billets sur FanPass et alerte via Telegram
dès qu'au moins MIN_QUANTITY billets sont proposés à un prix unitaire < MAX_PRICE.

Usage:
    python ticket_watcher.py

Configuration via .env (voir .env.example) :
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TICKET_URL, MAX_PRICE, MIN_QUANTITY
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

TICKET_URL = os.environ["TICKET_URL"]
MAX_PRICE = float(os.environ.get("MAX_PRICE", "250"))
MIN_QUANTITY = int(os.environ.get("MIN_QUANTITY", "2"))
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

STATE_FILE = Path(__file__).parent / "state.json"

# La page rend chaque billet sur plusieurs lignes, ex:
#   Virage Inférieur (General Admission)
#   F
#   4 Tickets
#   E-Billet
#   €235.2
#   /prix unit.
SECTION_RE = re.compile(r".+\(.+\)\s*$")
QTY_RE = re.compile(r"^(\d+)\s+Tickets?\b")
PRICE_RE = re.compile(r"^€\s*([\d]+[.,]?\d*)\s*$")


def fetch_page_text(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60_000)
        # Charge davantage de billets si le bouton existe
        for _ in range(5):
            btn = page.get_by_text("Afficher plus de tickets", exact=False)
            if btn.count() == 0:
                break
            try:
                btn.first.click(timeout=3_000)
                page.wait_for_timeout(1_000)
            except Exception:
                break
        text = page.inner_text("body")
        browser.close()
        return text


def find_matching_offers(text: str) -> list[dict]:
    lines = [ln.strip() for ln in text.splitlines()]
    offers = []
    last_section = None
    for i, line in enumerate(lines):
        if line and SECTION_RE.match(line) and not QTY_RE.match(line):
            last_section = line
            continue
        qty_match = QTY_RE.match(line)
        if not qty_match:
            continue
        qty = int(qty_match.group(1))
        price = None
        for j in range(i + 1, min(i + 6, len(lines))):
            price_match = PRICE_RE.match(lines[j])
            if price_match:
                price = float(price_match.group(1).replace(",", "."))
                break
        if price is not None and qty >= MIN_QUANTITY and price < MAX_PRICE:
            offers.append({"section": last_section or "?", "qty": qty, "price": price})
    return offers


def load_state() -> set[str]:
    if not STATE_FILE.exists():
        return set()
    raw = STATE_FILE.read_text(encoding="utf-8").strip()
    if not raw:
        return set()
    return set(json.loads(raw))


def save_state(signatures: set[str]) -> None:
    STATE_FILE.write_text(json.dumps(sorted(signatures)), encoding="utf-8")


def send_telegram_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=15)
    resp.raise_for_status()


def main() -> int:
    text = fetch_page_text(TICKET_URL)
    offers = find_matching_offers(text)

    if not offers:
        print("Aucune offre correspondante trouvée.")
        return 0

    already_notified = load_state()
    new_offers = [
        o for o in offers if f'{o["section"]}|{o["qty"]}|{o["price"]}' not in already_notified
    ]

    if not new_offers:
        print(f"{len(offers)} offre(s) trouvée(s), déjà notifiées.")
        return 0

    lines = ["🎟️ Nouveaux billets disponibles sur FanPass !"]
    for o in new_offers:
        lines.append(f'- {o["section"]}: {o["qty"]} billets à {o["price"]:.2f}€/unité')
    lines.append(TICKET_URL)

    send_telegram_message("\n".join(lines))
    print(f"Notification envoyée pour {len(new_offers)} nouvelle(s) offre(s).")

    already_notified.update(f'{o["section"]}|{o["qty"]}|{o["price"]}' for o in new_offers)
    save_state(already_notified)
    return 0


if __name__ == "__main__":
    sys.exit(main())
