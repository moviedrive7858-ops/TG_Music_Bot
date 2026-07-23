import os
import asyncio
import threading
from flask import Flask, jsonify
from pyrogram import Client, filters
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioQuality, MediaStream
from yt_dlp import YoutubeDL

# Flask Web Server setup
app = Flask(__name__)

@app.route('/')
def home():
    return "Telegram Music Bot is Live!"

@app.route('/ping')
def ping():
    return jsonify({"status": "alive"}), 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# Environment Variables
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")

# Telegram Clients Initializations
bot = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)

# PyTgCalls Client
call = PyTgCalls(user)

queues = {}

def get_audio_url(query):
    ydl_opts = {'format': 'bestaudio/best', 'quiet': True}
    with YoutubeDL(ydl_opts) as ydl:
        if not query.startswith("http"):
            query = f"ytsearch:{query}"
        info = ydl.extract_info(query, download=False)
        if 'entries' in info:
            info = info['entries'][0]
        return info['url'], info['title']

async def play_next(chat_id):
    if chat_id in queues and len(queues[chat_id]) > 0:
        next_song = queues[chat_id].pop(0)
        url, title = get_audio_url(next_song)
        await call.play(
            chat_id,
            MediaStream(
                url,
                video_flags=MediaStream.Flags.IGNORE,
                audio_parameters=AudioQuality.HIGH
            )
        )
        await bot.send_message(chat_id, f"🎵 အခုဖွင့်နေသည်: **{title}**")
    else:
        await call.leave_call(chat_id)

@bot.on_message(filters.command("play") & filters.group)
async def play(_, message):
    chat_id = message.chat.id
    query = " ".join(message.command[1:])
    if not query:
        return await message.reply_text("ကျေးဇူးပြုပြီး သီချင်းနာမည် သို့မဟုတ် URL ထည့်ပါ။")

    msg = await message.reply_text("🔎 သီချင်းရှာဖွေနေပါသည်...")
    try:
        url, title = get_audio_url(query)
        if chat_id in queues and len(queues[chat_id]) > 0:
            queues[chat_id].append(query)
            return await msg.edit(f"➕ Queue ထဲသို့ပေါင်းထည့်ပြီးပါပြီ: **{title}**")
        
        queues[chat_id] = []
        await call.play(
            chat_id,
            MediaStream(
                url,
                video_flags=MediaStream.Flags.IGNORE,
                audio_parameters=AudioQuality.HIGH
            )
        )
        await msg.edit(f"🎶 စတင်ဖွင့်နေပါပြီ: **{title}**")
    except Exception as e:
        await msg.edit(f"❌ အမှားအယွင်းရှိပါသည်: {str(e)}")

@bot.on_message(filters.command("next") & filters.group)
async def skip(_, message):
    chat_id = message.chat.id
    if chat_id in queues:
        await message.reply_text("⏭️ နောက်သီချင်းသို့ ကျော်နေပါသည်...")
        await play_next(chat_id)
    else:
        await message.reply_text("❌ Queue ထဲမှာ သီချင်းမရှိပါ။")

@bot.on_message(filters.command("stop") & filters.group)
async def stop(_, message):
    chat_id = message.chat.id
    try:
        queues[chat_id] = []
        await call.leave_call(chat_id)
        await message.reply_text("⏹️ သီချင်းခဏရပ်ပြီး Voice Call မှထွက်လိုက်ပါပြီ။")
    except:
        await message.reply_text("❌ မည်သည့် Voice Call မှ ဖွင့်မထားပါ။")

async def main():
    # Flask app ကို background thread ဖြင့် စတင်ခြင်း
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Telegram Clients များကို စတင်ခြင်း
    await bot.start()
    await user.start()
    await call.start()
    print(">>> BOT IS FULLY ONLINE & RUNNING <<<")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
