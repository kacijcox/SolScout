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
import asyncio
from aioflask import Flask

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

# Initialize the bot
bot = Bot(token=TELEGRAM_TOKEN)

async def test_bot_connection():
    """Test the bot connection and configuration"""
    try:
        bot_info = await bot.get_me()
        logger.debug(f"Bot connection successful. Bot name: {bot_info.first_name}")
        return True
    except Exception as e:
        logger.error(f"Bot connection failed: {str(e)}")
        return False

@app.route("/")
async def home():
    return "Solana Scout Bot is running!"

@app.route("/test")
async def test():
    try:
        await bot.send_message(chat_id=CHAT_ID, text="Test message from bot")
        logger.debug("Test message sent successfully")
        return "Test message sent successfully!"
    except Exception as e:
        logger.error(f"Test message failed: {str(e)}")
        return f"Error sending message: {str(e)}"

@app.route("/botinfo")
async def botinfo():
    try:
        bot_info = await bot.get_me()
        chat_info = await bot.get_chat(chat_id=CHAT_ID)
        return f"""
        Bot Information:
        Name: {bot_info.first_name}
        Username: {bot_info.username}
        Current CHAT_ID: {CHAT_ID}
        Chat Type: {chat_info.type}
        Chat Title: {getattr(chat_info, 'title', 'N/A')}
        """
    except Exception as e:
        logger.error(f"Error getting bot info: {str(e)}")
        return f"Error: {str(e)}"

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

async def send_alert(coin_name, volume, pair_url):
    """Send an alert message to Telegram."""
    try:
        message = (
            f"🚨 *New Solana Coin Alert* 🚨\n"
            f"Coin: {coin_name}\n"
            f"Volume in the first hour: ${volume:,.0f}\n"
            f"Details: [View on DEX Screener]({pair_url})"
        )
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
        logger.debug(f"Alert sent successfully for {coin_name}")
    except Exception as e:
        logger.error(f"Failed to send alert: {str(e)}")

async def check_new_coins():
    """Fetch data from DEX Screener and send alerts for new Solana coins."""
    url = "https://api.dexscreener.com/latest/dex/search?q=solana"  # Solana pairs
    alerted_coins = load_alerted_coins()
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        logger.debug(f"Successfully fetched data from DEX Screener")
        
        current_time = datetime.now(timezone.utc)
        
        for pair in data.get("pairs", []):
            if pair.get("chainId") != "solana":
                continue
            
            coin_name = pair["baseToken"]["name"]
            volume = float(pair.get("volume", {}).get("h24", 0))
            creation_timestamp = pair.get("pairCreatedAt", 0)
            pair_url = pair.get("url", "N/A")
            
            if not creation_timestamp:
                continue
            
            creation_time = datetime.fromtimestamp(creation_timestamp / 1000, tz=timezone.utc)
            age_in_minutes = (current_time - creation_time).total_seconds() / 60
            
            if age_in_minutes <= 60 and volume > 500000 and coin_name not in alerted_coins:
                await send_alert(coin_name, volume, pair_url)
                alerted_coins.add(coin_name)
                logger.debug(f"New coin detected and alert sent: {coin_name}")
        
        save_alerted_coins(alerted_coins)
    
    except requests.RequestException as e:
        logger.error(f"Error fetching data from DEX Screener: {e}")

async def run_bot_periodically():
    """Run the bot check every 15 minutes"""
    if not await test_bot_connection():
        logger.error("Bot initialization failed")
        return

    while True:
        try:
            logger.debug("Starting periodic check")
            await check_new_coins()
        except Exception as e:
            logger.error(f"Error in bot execution: {e}")
        await asyncio.sleep(900)  # Sleep for 15 minutes

if __name__ == "__main__":
    # Create event loop
    loop = asyncio.get_event_loop()
    
    # Start the bot checking task
    loop.create_task(run_bot_periodically())
    
    # Start the Flask server
    app.run(host="0.0.0.0", port=PORT)