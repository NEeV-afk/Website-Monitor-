import time
import os
os.system("pip install telebot requests pyTelegramBotAPI pymongo")
os.system("clear")
import requests
import logging
from telebot import TeleBot
from pymongo import MongoClient
from threading import Thread
from bson import ObjectId
import re

# Telegram bot token and MongoDB connection details
BOT_TOKEN = "8120748600:AAHzL3D0_ZH9qljumss8ePi5v9e6eZr5Src"
MONGO_URL = "mongodb+srv://botplays:botplays@vulpix.ffdea.mongodb.net/?retryWrites=true&w=majority&appName=Vulpix"

# Admin list (Telegram user IDs)
ADMINS = [6897739611]  # Replace with admin IDs

# Initialize the Telegram bot and MongoDB client
bot = TeleBot(BOT_TOKEN)
client = MongoClient(MONGO_URL)
db = client.website_monitoring  # Database name
websites_collection = db.websites  # Collection for website monitoring
users_collection = db.users  # Collection for tracking users

# Configure logging
logging.basicConfig(
    filename="monitor.log",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

def check_website_status(website_url, retries=3):
    """
    Checks if the website is reachable.
    Returns True if the website is up, False otherwise.
    Retries a few times if a network error occurs.
    """
    for attempt in range(retries):
        try:
            response = requests.get(website_url, timeout=10)
            return response.status_code == 200
        except requests.RequestException as e:
            logging.warning(f"Error checking website {website_url}: {e}")
            if attempt < retries - 1:
                time.sleep(5)  # Wait before retrying
    return False

def send_telegram_message(chat_id, message):
    """
    Sends a message to the specified Telegram chat.
    Handles any API errors gracefully.
    """
    try:
        bot.send_message(chat_id, message)
    except Exception as e:
        logging.error(f"Error sending message to {chat_id}: {e}")

@bot.message_handler(commands=['start'])
def handle_start(message):
    """
    Handles the /start command.
    Sends a personalized welcome message.
    """
    chat_id = message.chat.id
    first_name = message.from_user.first_name

    # Add user to the users collection
    users_collection.update_one({"chat_id": chat_id}, {"$set": {"first_name": first_name}}, upsert=True)

    try:
        bot.send_message(chat_id, f"Welcome {first_name}🥰!\n\n"
                                  "You Can Monitor Your Websites And Get Notified If They Goes Down🖥️.\n\n"
                                  "Use /help To Use The Bot ")
    except Exception as e:
        logging.error(f"Error handling /start for chat {chat_id}: {e}")

@bot.message_handler(commands=['addwebsite'])
def handle_addwebsite(message):
    """
    Handles the /addwebsite command to add a website for monitoring.
    """
    chat_id = message.chat.id
    try:
        website_url = message.text.split()[1]
        if not website_url.startswith("http"):
            bot.send_message(chat_id, "Please Provide A Valid URL (starting with http or https).")
            return
        # Add the website to the database
        websites_collection.insert_one({
            "chat_id": chat_id,
            "website_url": website_url,
            "last_checked_time": 0,
            "last_update_time": 0
        })
        bot.send_message(chat_id, f"Website Monitoring Started For URL: {website_url}")
    except IndexError:
        bot.send_message(chat_id, "Please Provide A Valid URL. Example:\n/addwebsite <url>")
    except Exception as e:
        logging.error(f"Error adding website for chat {chat_id}: {e}")
        bot.send_message(chat_id, "An error occurred while adding the website.")

@bot.message_handler(commands=['list'])
def handle_list(message):
    """
    Handles the /list command to display monitored websites for the user.
    """
    chat_id = message.chat.id
    try:
        websites = list(websites_collection.find({"chat_id": chat_id}))
        if not websites:
            bot.send_message(chat_id, "You Are Not Monitoring Any Websites🖥️.")
            return

        response = "Your Monitored Websites:\n"
        for website in websites:
            response += f"- ID: {website['_id']} | URL: {website['website_url']}\n"
        bot.send_message(chat_id, response)
    except Exception as e:
        logging.error(f"Error listing websites for chat {chat_id}: {e}")
        bot.send_message(chat_id, "An error occurred while fetching your monitored websites.")

@bot.message_handler(commands=['remove'])
def handle_remove(message):
    """
    Handles the /remove command to remove a monitored website.
    """
    chat_id = message.chat.id
    try:
        website_id = message.text.split()[1]
        result = websites_collection.delete_one({"_id": ObjectId(website_id), "chat_id": chat_id})
        if result.deleted_count > 0:
            bot.send_message(chat_id, "The Website Has Been Removed.")
        else:
            bot.send_message(chat_id, "Website not found or you don't have permission to remove it.")
    except IndexError:
        bot.send_message(chat_id, "Please Provide A Valid Website ID🥴. Example:\n/remove <website_id>")
    except Exception as e:
        logging.error(f"Error removing website for chat {chat_id}: {e}")
        bot.send_message(chat_id, "An error occurred while removing the website.")
        
@bot.message_handler(commands=['help'])
def handle_help(message):
    """
    Handles the /help command.
    Sends a list of all available commands to the user.
    """
    chat_id = message.chat.id

    try:
        bot.send_message(
            chat_id,
            "Here are the available commands:\n\n"
            "/start - Start The Bot And Get A Welcome Message.\n"
            "/addwebsite <url> - Add a website to monitor.\n"
            "/list - List's All Websites You Are Monitoring.\n"
            "/remove <website_id> - Remove A Monitored Website.\n\n"
            "Admins Only:\n"
            "/broadcast <message> - Onyl Admin Can Send."
        )
    except Exception as e:
        logging.error(f"Error handling /help for chat {chat_id}: {e}")
        
@bot.message_handler(commands=['broadcast'])
def handle_broadcast(message):
    """
    Handles the /broadcast command to send a message to all users.
    Only accessible by admins.
    """
    chat_id = message.chat.id
    if chat_id not in ADMINS:
        bot.send_message(chat_id, "You Do Not Have Permission To Use This Command❌")
        return

    try:
        broadcast_message = " ".join(message.text.split()[1:])
        if not broadcast_message:
            bot.send_message(chat_id, "Please Provide A Message To Broadcast. Example:\n/Broadcast <message>")
            return

        users = users_collection.find()
        sent_count = 0  # Initialize counter for successful messages

        for user in users:
            try:
                send_telegram_message(user["chat_id"], f"{broadcast_message}")
                sent_count += 1
            except Exception as e:
                logging.error(f"Error sending broadcast to {user['chat_id']}: {e}")

        bot.send_message(chat_id, f"Broadcast message sent successfully to {sent_count} users📢")
    except Exception as e:
        logging.error(f"Error broadcasting message: {e}")
        bot.send_message(chat_id, "An error occurred while broadcasting the message.")

def monitor_websites():
    """
    Monitors all websites for all users in the database.
    Sends alerts or status updates as needed.
    """
    while True:
        try:
            websites = websites_collection.find()
            for website in websites:
                chat_id = website["chat_id"]
                website_url = website["website_url"]
                last_checked_time = website.get("last_checked_time", 0)
                last_update_time = website.get("last_update_time", 0)
                current_time = time.time()

                # Check website status
                if current_time - last_checked_time >= 30:  # Check interval: 30 seconds
                    is_up = check_website_status(website_url)
                    websites_collection.update_one({"_id": website["_id"]}, {"$set": {"last_checked_time": current_time}})

                    if not is_up:
                        send_telegram_message(chat_id, f"⚠️ Alert: The Website {website_url} Is Down!📉")
                    elif current_time - last_update_time >= 6 * 60 * 60:  # 6-hour update
                        send_telegram_message(chat_id, f"✅ Status Update: The website {website_url} is up and running!")
                        websites_collection.update_one({"_id": website["_id"]}, {"$set": {"last_update_time": current_time}})

            time.sleep(5)  # Wait to reduce CPU usage
        except Exception as e:
            logging.error(f"Error in monitoring loop: {e}")
            time.sleep(10)  # Wait before restarting the loop

# Start monitoring in a separate thread
monitor_thread = Thread(target=monitor_websites)
monitor_thread.start()

# Start the bot
try:
    bot.polling(none_stop=True)
except Exception as e:
    logging.critical(f"Bot polling failed: {e}")
    