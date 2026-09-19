import json
import os
import urllib.request
from pathlib import Path

KUCOIN_URL = "https://api.kucoin.com/api/v3/currencies"
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

STATE_FILE = Path("status.json")


def get_kucoin_status():
    request = urllib.request.Request(
        KUCOIN_URL,
        headers={"User-Agent": "KuCoin-Deposit-Monitor/1.0"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    if data.get("code") != "200000":
        raise RuntimeError(f"KuCoin API error: {data}")

    statuses = {}

    for coin in data.get("data", []):
        currency = coin.get("currency")

        for chain in coin.get("chains", []):
            chain_id = chain.get("chainId") or chain.get("chainName")

            if not currency or not chain_id:
                continue

            key = f"{currency}:{chain_id}"
            statuses[key] = {
                "coin": currency,
                "network": chain.get("chainName") or chain_id,
                "enabled": bool(chain.get("isDepositEnabled"))
            }

    return statuses


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = json.dumps({
        "chat_id": CHAT_ID,
        "text": message
    }).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError("Telegram notification failed")


def load_previous():
    if not STATE_FILE.exists():
        return {}

    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def save_current(statuses):
    STATE_FILE.write_text(
        json.dumps(statuses, indent=2),
        encoding="utf-8"
    )


def main():
    current = get_kucoin_status()
    previous = load_previous()

    # First run: save current status without sending alerts.
    if not previous:
        save_current(current)
        print(f"Initial status saved: {len(current)} networks")
        return

    alerts = []

    for key, info in current.items():
        now_enabled = info["enabled"]

        if key in previous:
            was_enabled = previous[key]["enabled"]

            # ON -> OFF
            if was_enabled and not now_enabled:
                alerts.append(
                    f"🚨 KUCOIN DEPOSIT OFF\n\n"
                    f"Coin: {info['coin']}\n"
                    f"Network: {info['network']}"
                )

            # OFF -> ON
            elif not was_enabled and now_enabled:
                alerts.append(
                    f"✅ KUCOIN DEPOSIT ON\n\n"
                    f"Coin: {info['coin']}\n"
                    f"Network: {info['network']}"
                )

    for message in alerts:
        send_telegram(message)

    save_current(current)

    print(
        f"Checked {len(current)} networks | "
        f"Alerts sent: {len(alerts)}"
    )


if __name__ == "__main__":
    main()
