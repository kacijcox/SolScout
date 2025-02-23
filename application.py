import requests 
import os
import json
import logging
from telegram import Bot
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from fastapi import FastAPI
import asyncio
from typing import Dict, Any

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()

# Load environment variables from .env file
load_dotenv()

# Environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")  # Your chat or group ID
ALERTED_COINS_FILE = "alerted_coins.json"  # File to track alerted coins

# Debug logging
logger.debug(f"Starting application with TELEGRAM_TOKEN: {TELEGRAM_TOKEN[:4]}..." if TELEGRAM_TOKEN else "No token found")
logger.debug(f"CHAT_ID: {CHAT_ID}")

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

async def send_alert(coin_name: str, volume: float, pair_url: str):
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

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot_periodically())

async def run_bot_periodically():
    """Run the bot check every 15 minutes"""
    while True:
        try:
            logger.debug("Starting periodic check")
            await check_new_coins()
        except Exception as e:
            logger.error(f"Error in bot execution: {e}")
        await asyncio.sleep(900)  # Sleep for 15 minutes

@app.get("/")
async def root():
    return {"message": "Solana Scout Bot is running!"}

@app.get("/test")
async def test():
    try:
        await bot.send_message(chat_id=CHAT_ID, text="Test message from bot")
        logger.debug("Test message sent successfully")
        return {"message": "Test message sent successfully!"}
    except Exception as e:
        logger.error(f"Test message failed: {str(e)}")
        return {"error": str(e)}

@app.get("/botinfo")
async def botinfo():
    try:
        bot_info = await bot.get_me()
        chat_info = await bot.get_chat(chat_id=CHAT_ID)
        return {
            "bot_name": bot_info.first_name,
            "bot_username": bot_info.username,
            "chat_id": CHAT_ID,
            "chat_type": chat_info.type,
            "chat_title": getattr(chat_info, "title", "N/A")
        }
    except Exception as e:
        logger.error(f"Error getting bot info: {str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)