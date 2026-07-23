import os
import asyncio
import threading
from flask import Flask, jsonify
from pyrogram import Client, filters
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
from pytgcalls.types.stream import StreamEnded
from yt_dlp import YoutubeDL

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

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")

bot = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)
call = PyTgCalls(user)

queues = {}

# Async-safe extract info function
def _get_audio_url_sync(query):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'geo_bypass': True,
        'nocheckcertificate': True
    }
    with YoutubeDL(ydl_opts) as ydl:
        if not query.startswith("http"):
            query = f"ytsearch:{query}"
        info = ydl.extract_info(query, download=False)
        if 'entries' in info and info['entries']:
            info = info['entries'][0]
        return info['url'], info['title']

async def get_audio_url(query):
    # Event loop မခဲသွားအောင် thread သီးသန့်မှာ run ပေးခြင်း
    return await asyncio.to_thread(_get_audio_url_sync, query)

async def play_next(chat_id):
    if chat_id in queues and len(queues[chat_id]) > 0:
        next_song = queues[chat_id].pop(0)
        try:
            url, title = await get_audio_url(next_song)
            await call.play(chat_id, MediaStream(url))
            await bot.send_message(chat_id, f"🎵 အခုဖွင့်နေသည်: **{title}**")
        except Exception as e:
            await bot.send_message(chat_id, f"❌ သီချင်းဖွင့်ရာတွင် အမှားရှိပါသည်: {e}")
            await play_next(chat_id)
    else:
        try:
            await call.leave_call(chat_id)
        except:
            pass

# သီချင်းတစ်ပုဒ်ပြီးတိုင်း အလိုအလျောက် နောက်တစ်ပုဒ်ဖွင့်ရန် EventHandler
@call.on_stream_end()
async def stream_end_handler(_, update: StreamEnded):
    chat_id = update.chat_id
    await play_next(chat_id)

@bot.on_message(filters.command("play") & filters.group)
async def play(_, message):
    chat_id = message.chat.id
    query = " ".join(message.command[1:])
    if not query:
        return await message.reply_text("ကျေးဇူးပြုပြီး သီချင်းနာမည် သို့မဟုတ် URL ထည့်ပါ။")

    msg = await message.reply_text("🔎 သီချင်းရှာဖွေနေပါသည်...")
    try:
        url, title = await get_audio_url(query)
        
        # ဖွင့်ထားပြီးသား သီချင်းရှိ/မရှိ စစ်ဆေးခြင်း Logic ပြင်ဆင်ချက်
        if chat_id in queues:
            queues[chat_id].append(query)
            return await msg.edit(f"➕ Queue ထဲသို့ပေါင်းထည့်ပြီးပါပြီ: **{title}**")
        
        queues[chat_id] = []
        await call.play(chat_id, MediaStream(url))
        await msg.edit(f"🎶 စတင်ဖွင့်နေပါပြီ: **{title}**")
    except Exception as e:
        await msg.edit(f"❌ အမှားအယွင်းရှိပါသည်: {str(e)}")

@bot.on_message(filters.command("next") & filters.group)
async def skip(_, message):
    chat_id = message.chat.id
    if chat_id in queues and len(queues[chat_id]) > 0:
        await message.reply_text("⏭️ နောက်သီချင်းသို့ ကျော်နေပါသည်...")
        await play_next(chat_id)
    else:
        await message.reply_text("❌ Queue ထဲမှာ နောက်ထပ်သီချင်းမရှိပါ။")

@bot.on_message(filters.command("stop") & filters.group)
async def stop(_, message):
    chat_id = message.chat.id
    try:
        if chat_id in queues:
            del queues[chat_id]
        await call.leave_call(chat_id)
        await message.reply_text("⏹️ သီချင်းခဏရပ်ပြီး Voice Call မှထွက်လိုက်ပါပြီ။")
    except:
        await message.reply_text("❌ မည်သည့် Voice Call မှ ဖွင့်မထားပါ။")

async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    
    await bot.start()
    await user.start()
    await call.start()
    print(">>> BOT IS FULLY ONLINE & RUNNING <<<")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
