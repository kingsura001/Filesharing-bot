from dotenv import load_dotenv
load_dotenv()

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
import os, time

# Configuration
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
FORCE_SUB_CHANNEL = os.getenv("FORCE_SUB_CHANNEL")  # Username without @
LOG_CHANNEL = int(os.getenv("LOG_CHANNEL"))
ADMIN_IDS = list(map(int, os.getenv("6954573092").split()))  # Comma-separated IDs
DELETE_TIME = int(os.getenv("DELETE_TIME", 3600))
MONGO_URL = os.getenv("MONGO_URL")

# Database
mongo = MongoClient(MONGO_URL)
db = mongo["file_store"]
files_col = db["files"]
users_col = db["users"]

# Bot Client
bot = Client("file_store_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

scheduler = BackgroundScheduler()
scheduler.start()

# Utils
def is_admin(user_id):
    return user_id in ADMIN_IDS

def schedule_deletion(file_id):
    scheduler.add_job(delete_file, 'date', run_date=time.time() + DELETE_TIME, args=[file_id])

def delete_file(file_id):
    files_col.delete_one({"_id": file_id})

# Handlers
@bot.on_message(filters.private & filters.command("start"))
async def start_cmd(client, message: Message):
    user_id = message.from_user.id
    users_col.update_one({"_id": user_id}, {"$set": {"joined": True}}, upsert=True)

    if len(message.command) > 1:
        file_id = message.command[1].replace("file_", "")
        file_data = files_col.find_one({"_id": file_id})
        if not file_data:
            return await message.reply("File not found or has expired.")

        await message.reply_document(
            file_data['file_id'],
            caption=file_data.get("caption", ""),
            protect_content=True
        )
        return

    await message.reply("Welcome to the File Store Bot! Send me a file to get started.")

@bot.on_message(filters.private & filters.document & filters.user(ADMIN_IDS))
async def save_file(client, message: Message):
    file = message.document
    file_id = str(file.file_id)
    file_unique = file.file_unique_id
    user_id = message.from_user.id
    caption = message.caption or ""

    doc = {
        "_id": file_unique,
        "file_id": file_id,
        "user_id": user_id,
        "caption": caption,
        "timestamp": time.time()
    }

    files_col.insert_one(doc)
    schedule_deletion(file_unique)

    link = f"https://t.me/{client.me.username}?start=file_{file_unique}"
    await message.reply(f"File saved! Share this link: {link}")
    await client.send_message(LOG_CHANNEL, f"New file saved by {user_id}: {link}")

@bot.on_message(filters.private & filters.command("stats") & filters.user(ADMIN_IDS))
async def stats_cmd(client, message: Message):
    users = users_col.count_documents({})
    files = files_col.count_documents({})
    await message.reply(f"Users: {users}\nFiles: {files}")

@bot.on_message(filters.private & filters.command("broadcast") & filters.user(ADMIN_IDS))
async def broadcast_cmd(client, message: Message):
    if not message.reply_to_message:
        return await message.reply("Reply to a message to broadcast it.")

    users = users_col.find()
    count = 0
    for user in users:
        try:
            await message.reply_to_message.copy(chat_id=user['_id'])
            count += 1
        except:
            continue
    await message.reply(f"Broadcasted to {count} users.")

bot.run()
