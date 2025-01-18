import requests 
import os
import json
import logging
from telegram import Bot
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from flask import Flask
import threading
import time

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Load environment variables from .env file
load_dotenv()

# Environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")  # Your chat or group ID
ALERTED_COINS_FILE = "alerted_coins.json"  # File to track alerted coins
PORT = int(os.environ.get("PORT", 5000))

# Debug logging
logger.debug(f"Starting application with TELEGRAM_TOKEN: {TELEGRAM_TOKEN[:4]}..." if TELEGRAM_TOKEN else "No token found")
logger.debug(f"CHAT_ID: {CHAT_ID}")

try:
    # Initialize the bot
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.debug("Bot initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize bot: {str(e)}")

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

def send_alert(coin_name, volume, pair_url):
    """Send an alert message to Telegram."""
    try:
        message = (
            f"🚨 *New Solana Coin Alert* 🚨\n"
            f"Coin: {coin_name}\n"
            f"Volume in the first hour: ${volume:,.0f}\n"
            f"Details: [View on DEX Screener]({pair_url})"
        )
        bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
        logger.debug(f"Alert sent successfully for {coin_name}")
    except Exception as e:
        logger.error(f"Failed to send alert: {str(e)}")

def check_new_coins():
    """Fetch data from DEX Screener and send alerts for new Solana coins."""
    url = "https://api.dexscreener.com/latest/dex/search?q=solana"  # Solana pairs
    alerted_coins = load_alerted_coins()
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        logger.debug(f"Successfully fetched data from DEX Screener")
        
        # Current UTC time (timezone-aware)
        current_time = datetime.now(timezone.utc)
        
        # Iterate through pairs and filter for Solana
        for pair in data.get("pairs", []):
            # Check if the chainId is Solana
            if pair.get("chainId") != "solana":
                continue
            
            # Extract required fields
            coin_name = pair["baseToken"]["name"]
            volume = float(pair.get("volume", {}).get("h24", 0))
            creation_timestamp = pair.get("pairCreatedAt", 0)
            pair_url = pair.get("url", "N/A")
            
            # Skip if no creation timestamp
            if not creation_timestamp:
                continue
            
            # Convert creation timestamp to datetime (timezone-aware)
            creation_time = datetime.fromtimestamp(creation_timestamp / 1000, tz=timezone.utc)
            age_in_minutes = (current_time - creation_time).total_seconds() / 60
            
            # Alert only for new coins within the first hour with volume > $500,000
            if age_in_minutes <= 60 and volume > 500000 and coin_name not in alerted_coins:
                send_alert(coin_name, volume, pair_url)
                alerted_coins.add(coin_name)
                logger.debug(f"New coin detected and alert sent: {coin_name}")
        
        # Save the updated list of alerted coins
        save_alerted_coins(alerted_coins)
    
    except requests.RequestException as e:
        logger.error(f"Error fetching data from DEX Screener: {e}")

# Flask routes
@app.route("/")
def home():
    return "Solana Scout Bot is running!"

@app.route("/test")
def test():
    try:
        bot.send_message(chat_id=CHAT_ID, text="Test message from bot")
        return "Test message sent successfully!"
    except Exception as e:
        logger.error(f"Test message failed: {str(e)}")
        return f"Error sending message: {str(e)}"

@app.route("/botinfo")
def botinfo():
    try:
        bot_info = bot.get_me()
        chat_info = bot.get_chat(chat_id=CHAT_ID)
        return f"""
        Bot Information:
        Name: {bot_info.first_name}
        Username: {bot_info.username}
        Current CHAT_ID: {CHAT_ID}
        Chat Type: {chat_info.type}
        Chat Title: {chat_info.title if hasattr(chat_info, 'title') else 'N/A'}
        """
    except Exception as e:
        logger.error(f"Error getting bot info: {str(e)}")
        return f"Error: {str(e)}"

def run_bot_periodically():
    """Run the bot check every 15 minutes"""
    while True:
        try:
            logger.debug("Starting periodic check")
            check_new_coins()
        except Exception as e:
            logger.error(f"Error in bot execution: {e}")
        time.sleep(900)  # Sleep for 15 minutes

if __name__ == "__main__":
    # Start the bot checking thread
    bot_thread = threading.Thread(target=run_bot_periodically)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Start the Flask server
    app.run(host="0.0.0.0", port=PORT)