import os
import time
import asyncio
import logging
import glob
import shutil
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
import yt_dlp

# ----------------------------------------------------
# 1. LOGGING & SETUP
# ----------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s"
)
logger = logging.getLogger("RenderUniversalBot")

load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
TARGET_GROUP_ID = os.getenv("TARGET_GROUP_ID")

if not all([API_ID, API_HASH, BOT_TOKEN, TARGET_GROUP_ID]):
    logger.critical("❌ Environment variables missing!")
    exit(1)

API_ID = int(API_ID)
TARGET_GROUP_ID = int(TARGET_GROUP_ID)

DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def auto_clean_server():
    """downloads folder auto clean"""
    files = glob.glob(os.path.join(DOWNLOAD_DIR, "*"))
    for f in files:
        try:
            if os.path.isfile(f) or os.path.islink(f):
                os.unlink(f)
            elif os.path.isdir(f):
                shutil.rmtree(f)
        except Exception:
            pass

auto_clean_server()

app = Client(
    "render_universal_downloader",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

download_lock = asyncio.Lock()
last_edit_time = {}

# ----------------------------------------------------
# 2. REAL-TIME ANIMATED PROGRESS BAR
# ----------------------------------------------------
async def update_status_msg(current, total, status_msg: Message, action_type: str, speed_str: str = ""):
    now = time.time()
    msg_id = status_msg.id
    
    if msg_id in last_edit_time and (now - last_edit_time[msg_id]) < 3.5:
        return
    last_edit_time[msg_id] = now
    
    if total <= 0:
        return

    percentage = (current / total) * 100
    filled_blocks = int(percentage // 10)
    empty_blocks = 10 - filled_blocks
    
    bar = "█" * filled_blocks + "▒" * empty_blocks
    current_mb = current / (1024 * 1024)
    total_mb = total / (1024 * 1024)
    
    speed_info = f"\n⚡ **Speed:** `{speed_str}`" if speed_str else ""

    text = (
        f"🚀 **Render Universal Engine** 🚀\n\n"
        f"📌 **Stage:** `{action_type}`\n"
        f"`[{bar}]` `{percentage:.1f}%`\n"
        f"📦 **Size:** `{current_mb:.1f} MB` / `{total_mb:.1f} MB`"
        f"{speed_info}\n"
        f"🖥️ **Host:** Render Cloud Container"
    )
    
    try:
        await status_msg.edit_text(text)
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception:
        pass

async def upload_progress_bar(current, total, status_msg: Message):
    await update_status_msg(current, total, status_msg, "⬆️ Uploading to Telegram")

# ----------------------------------------------------
# 3. YOUTUBE BYPASS & DOWNLOAD LOGIC
# ----------------------------------------------------
@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "🔥 **Render Universal Video Downloader Bot Active!** 🔥\n\n"
        "আমাকে ইউটিউব, ফেসবুক, ইনস্টাগ্রাম সহ যেকোনো লিংক দিন।"
    )

@app.on_message(filters.text & (filters.private | filters.group))
async def handle_download(client: Client, message: Message):
    if not message.text:
        return
        
    url = message.text.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        return

    if download_lock.locked():
        await message.reply_text("⏳ অন্য একটি ভিডিও ডাউনলোড হচ্ছে, অনুগ্রহ করে একটু অপেক্ষা করুন...")

    async with download_lock:
        auto_clean_server()
        status_msg = await message.reply_text("🔎 **লিংক বিশ্লেষণ করা হচ্ছে...**")
        file_path = None

        try:
            loop = asyncio.get_event_loop()

            def ytdlp_hook(d):
                if d['status'] == 'downloading':
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    speed = d.get('_speed_str', '').strip()
                    
                    if total > 0:
                        asyncio.run_coroutine_threadsafe(
                            update_status_msg(downloaded, total, status_msg, "📥 Downloading to Server", speed),
                            loop
                        )

            # 🔥 YOUTUBE ANTI-BOT BYPASS CONFIGURATION:
            ydl_opts = {
                'format': 'best[ext=mp4][filesize<450M]/best[filesize<450M]/best',
                'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
                'progress_hooks': [ytdlp_hook],
                'quiet': True,
                'no_warnings': True,
                'nocheckcertificate': True,
                # Simulate Android/iOS clients to bypass YouTube 'Sign in' requirement
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'ios', 'web']
                    }
                },
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            }

            def fetch_video():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    return info, filename

            info_dict, file_path = await loop.run_in_executor(None, fetch_video)

            if not file_path or not os.path.exists(file_path):
                raise FileNotFoundError("ভিডিও ডাউনলোড সম্পন্ন করা যায়নি।")

            duration = int(info_dict.get('duration', 0) or 0)
            width = int(info_dict.get('width', 0) or 0)
            height = int(info_dict.get('height', 0) or 0)
            title = info_dict.get('title', 'Downloaded Video')

            caption = (
                f"🎥 **{title}**\n\n"
                f"👤 **Requested by:** {message.from_user.mention if message.from_user else 'User'}\n"
                f"⚡ **Processed by:** Render Cloud Engine"
            )

            await status_msg.edit_text("⬆️ **টেলিগ্রাম গ্রুপে আপলোড করা হচ্ছে...**")

            destination_chat = TARGET_GROUP_ID if message.chat.type.value == "private" else message.chat.id

            await client.send_video(
                chat_id=destination_chat,
                video=file_path,
                caption=caption,
                duration=duration,
                width=width,
                height=height,
                supports_streaming=True,
                progress=upload_progress_bar,
                progress_args=(status_msg,)
            )

            await status_msg.edit_text("✅ **ভিডিও সফলভাবে গ্রুপে পাঠানো হয়েছে এবং সার্ভার সম্পূর্ণ ক্লিয়ার করা হয়েছে!**")

        except Exception as e:
            logger.error(f"Error: {str(e)}")
            await status_msg.edit_text(f"❌ **Error:**\n`{str(e)}`")

        finally:
            auto_clean_server()
            if status_msg.id in last_edit_time:
                del last_edit_time[status_msg.id]

if __name__ == "__main__":
    logger.info("Starting Render Bot Engine...")
    app.run()
