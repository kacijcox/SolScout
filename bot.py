import requests
import os
import json
from telegram import Bot
from datetime import datetime, timedelta

# Environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")  # Your chat or group ID
ALERTED_COINS_FILE = "alerted_coins.json"  # File to track alerted coins

# Initialize the bot
bot = Bot(token=TELEGRAM_TOKEN)

def load_alerted_coins():
    """Load the list of alerted coins from a file."""
    if os.path.exists(ALERTED_COINS_FILE):
        with open(ALERTED_COINS_FILE, "r") as file:
            return set(json.load(file))
    return set()

def save_alerted_coins(alerted_coins):
    """Save the list of alerted coins to a file."""
    with open(ALERTED_COINS_FILE, "w") as file:
        json.dump(list(alerted_coins), file)

def send_alert(coin_name, volume):
    """Send an alert message to Telegram."""
    message = (f"🚨 *New Solana Coin Alert* 🚨\n"
               f"Coin: {coin_name}\n"
               f"Volume in the first hour: ${volume:,.0f}\n"
               f"Detected on DEX Screener.")
    bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")

def check_new_solana_coins():
    """Fetch data from DEX Screener and send alerts for new Solana coins."""
    url = "https://api.dexscreener.com/latest/dex/pairs/solana"  # Solana-specific endpoint
    alerted_coins = load_alerted_coins()

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        for coin in data.get("pairs", []):
            coin_name = coin["baseToken"]["name"]
            volume = float(coin.get("hourlyVolumeUSD", 0))
            creation_timestamp = coin.get("pairCreationTimestamp")  # Adjust field name if needed

            # Skip coins without a creation timestamp
            if not creation_timestamp:
                continue

            # Convert creation timestamp to datetime
            creation_time = datetime.fromtimestamp(creation_timestamp)
            current_time = datetime.now()
            age_in_minutes = (current_time - creation_time).total_seconds() / 60

            # Alert only for new Solana coins within the first hour with volume > 500k
            if age_in_minutes <= 60 and volume > 500000 and coin_name not in alerted_coins:
                send_alert(coin_name, volume)
                alerted_coins.add(coin_name)  # Mark this coin as alerted

        # Save the updated list of alerted coins
        save_alerted_coins(alerted_coins)

    except requests.RequestException as e:
        print(f"Error fetching data from DEX Screener: {e}")

if __name__ == "__main__":
    check_new_solana_coins()
