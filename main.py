import os
import re
import asyncio
import logging
import yt_dlp
from typing import Dict, Optional, Tuple
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ChatAction
from telegram.error import TelegramError

# إعدادات التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================ الإعدادات ================
BOT_TOKEN = "8754784918:AAHO0ZuDvsSlp64DXYjSLAdrj9AWpMY_RBI"
CHANNEL_ID = "-1003523278791"
CHANNEL_LINK = "https://t.me/A7adi"

# ================ المنصات ================
PLATFORMS = {
    "youtube": {
        "name": "YouTube",
        "emoji": "🎬",
        "patterns": [r"(youtube\.com|youtu\.be)"]
    },
    "instagram": {
        "name": "Instagram",
        "emoji": "📸",
        "patterns": [r"(instagram\.com|instagr\.am)"]
    },
    "facebook": {
        "name": "Facebook",
        "emoji": "📘",
        "patterns": [r"(facebook\.com|fb\.com|fb\.watch)"]
    },
    "X": {
        "name": "X",
        "emoji": "🐦",
        "patterns": [r"(x\.com)"]
    }
}

# ================ إعدادات yt-dlp ================
def get_ydl_opts(quality: str = "medium"):
    quality_settings = {
        "high": {
            'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]',
            'outtmpl': 'downloads/%(title)s_%(id)s_hd.%(ext)s'
        },
        "medium": {
            'format': 'best[height<=720][ext=mp4]/best[height<=720]/best',
            'outtmpl': 'downloads/%(title)s_%(id)s_sd.%(ext)s'
        },
        "low": {
            'format': 'worst[ext=mp4]/worst',
            'outtmpl': 'downloads/%(title)s_%(id)s_low.%(ext)s'
        }
    }
    
    opts = quality_settings.get(quality, quality_settings["medium"])
    opts.update({
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'ignoreerrors': True,
        'no_color': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
    })
    return opts

# ================ دوال التحقق من الاشتراك ================
async def is_subscribed(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except TelegramError:
        return False

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    
    if await is_subscribed(user_id, context):
        return True
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📢 اشترك بالقناة", url=CHANNEL_LINK),
        InlineKeyboardButton("🔄 تحقق", callback_data="check_sub")
    ]])
    
    await update.message.reply_text(
        "⚠️ عذراً، ما بتقدر تستخدم البوت!\n\n"
        "لازم تشترك في قناة المطور أولاً\n\n"
        "👇 اضغط على الزر أدناه للاشتراك ثم تحقق",
        reply_markup=keyboard
    )
    return False

# ================ تحميل الفيديو ================
async def download_video(url: str, quality: str) -> Tuple[Optional[str], Optional[Dict]]:
    try:
        ydl_opts = get_ydl_opts(quality)
        
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                if not info:
                    return None, None
                
                if 'entries' in info:
                    info = info['entries'][0]
                    if not info:
                        return None, None
                
                filename = ydl.prepare_filename(info)
                
                if not os.path.exists(filename):
                    for ext in ['mp4', 'webm', 'mkv']:
                        test_name = filename.rsplit('.', 1)[0] + f'.{ext}'
                        if os.path.exists(test_name):
                            filename = test_name
                            break
                
                return filename, info
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, download)
        
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None, None

# ================ كشف المنصة ================
def detect_platform(url: str) -> Optional[str]:
    url_lower = url.lower()
    for platform_key, platform_data in PLATFORMS.items():
        for pattern in platform_data['patterns']:
            if re.search(pattern, url_lower):
                return platform_key
    return None

# ================ أوامر البوت ================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_subscription(update, context):
        return
    
    user = update.effective_user
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎬 High (1080p)", callback_data="quality_high"),
            InlineKeyboardButton("🎬 Medium (720p)", callback_data="quality_medium"),
        ],
        [
            InlineKeyboardButton("📀 Low (480p)", callback_data="quality_low"),
        ]
    ])
    
    await update.message.reply_text(
        f" اررررحب {user.first_name}!\n\n"
        f"SM Downloader Bot \n\n"
        f"📅 {datetime.now().strftime('%Y-%m-%d')}\n\n"
        f"! Support: \n"
        f"> YouTube | Instagram | Facebook | X\n\n"
        f"! Choose Quality: ",
        reply_markup=keyboard
    )
    context.user_data['waiting_for_quality'] = True

async def quality_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    quality = query.data.replace("quality_", "")
    context.user_data['download_quality'] = quality
    context.user_data['waiting_for_quality'] = False
    
    keyboard = []
    row = []
    for i, (key, platform) in enumerate(PLATFORMS.items(), 1):
        row.append(InlineKeyboardButton(
            f"{platform['emoji']} {platform['name']}",
            callback_data=f"platform_{key}"
        ))
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"✅ تم اختيار الجودة: {quality.upper()}\n\n"
        f"اختر المنصة:",
        reply_markup=reply_markup
    )

async def platform_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    platform_key = query.data.replace("platform_", "")
    context.user_data['selected_platform'] = platform_key
    quality = context.user_data.get('download_quality', 'medium')
    
    await query.edit_message_text(
        f"{PLATFORMS[platform_key]['emoji']} تم اختيار {PLATFORMS[platform_key]['name']}\n\n"
        f"الجودة: {quality.upper()}\n\n"
        f"الآن أرسل رابط الفيديو\n\n"

        f"مثال:\nhttps://www.{platform_key}.com/..."
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "check_sub":
        user_id = query.from_user.id
        if await is_subscribed(user_id, context):
            await query.edit_message_text("✅ تم التحقق! استخدم /start")
        else:
            await query.answer("❌ لم تشترك بعد!", show_alert=True)
        return
    
    if data.startswith("quality_"):
        await quality_callback(update, context)
    elif data.startswith("platform_"):
        await platform_callback(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not await is_subscribed(user_id, context):
        await check_subscription(update, context)
        return
    
    if context.user_data.get('waiting_for_quality'):
        await update.message.reply_text(
            "⚠️ يرجى اختيار جودة التحميل أولاً!\n\n"
            "استخدم /start للبدء"
        )
        return
    
    url = update.message.text.strip()
    
    platform = context.user_data.get('selected_platform')
    if not platform:
        platform = detect_platform(url)
        if not platform:
            await update.message.reply_text(
                "❌ رابط غير مدعوم!\n\n"
                "المنصات المدعومة:\n"
                "YouTube, Instagram, Facebook, X\n\n"
                "استخدم /start لاختيار منصة"
            )
            return
    
    quality = context.user_data.get('download_quality', 'medium')
    
    # رسالة التحميل بدون Markdown معقد
    progress_msg = await update.message.reply_text(
        f"جاري تحميل الفيديو...\n"
        f"المنصة: {PLATFORMS[platform]['name']}\n"
        f"الجودة: {quality.upper()}\n"
        f"الرجاء الانتظار..."
    )
    
    await update.message.chat.send_action(action=ChatAction.UPLOAD_VIDEO)
    
    filename, info = await download_video(url, quality)
    
    if not filename or not os.path.exists(filename):
        await progress_msg.edit_text(
            "❌ فشل التحميل!\n\n"
            "الأسباب المحتملة:\n"
            "1- الرابط غير صحيح\n"
            "2- الفيديو خاص أو محذوف\n"
            "3- المنصة غير مدعومة\n\n"
            "استخدم /start للمحاولة مرة أخرى"
        )
        return
    
    file_size = os.path.getsize(filename) / (1024 * 1024)
    
    if file_size > 50:
        await progress_msg.edit_text(
            f"⚠️ الفيديو كبير جداً!\n"
            f"الحجم: {file_size:.1f}MB (الحد 50MB)\n\n"
            f"جرب جودة أقل من /start"
        )
        os.remove(filename)
        return
    
    video_title = info.get('title', 'فيديو')[:50] if info else 'فيديو'
    
    await progress_msg.edit_text(
        f"جاري رفع الفيديو...\n"
        f"العنوان: {video_title}\n"
        f"الحجم: {file_size:.1f}MB"
    )
    
    try:
        with open(filename, 'rb') as video_file:
            await update.message.reply_video(
                video=video_file,
                caption=f"✅ تم التحميل بنجاح!\n\n"
                       f"المصدر: {PLATFORMS[platform]['name']}\n"
                       f"العنوان: {video_title}\n"
                       f"الجودة: {quality.upper()}\n"
                       f"التاريخ: {datetime.now().strftime('%Y-%m-%d')}\n\n"
                       f"بوت التحميل الاحترافي",
                supports_streaming=True
            )
        
        os.remove(filename)
        await progress_msg.delete()
        
    except Exception as e:
        logger.error(f"Error sending video: {e}")
        await progress_msg.edit_text(
            f"❌ حدث خطأ أثناء رفع الفيديو!\n"
            f"الخطأ: {str(e)[:100]}\n\n"
            f"حاول مرة أخرى باستخدام /start"
        )
        if os.path.exists(filename):
            os.remove(filename)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("✅ تم الإلغاء!\n\nاستخدم /start للبدء من جديد")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 دليل الاستخدام:\n\n"
        "1- استخدم /start لبدء البوت\n"
        "2- اختر جودة التحميل\n"
        "3- اختر المنصة\n"
        "4- أرسل رابط الفيديو\n\n"
        "المنصات المدعومة:\n"
        "✅ YouTube\n"
        "✅ Instagram\n"
        "✅ Facebook\n"
        "✅ X\n"
        "الأوامر:\n"
        "/start - بدء البوت\n"
        "/cancel - إلغاء العملية\n"
        "/help - عرض المساعدة"
    )

# ================ التشغيل ================
async def post_init(application: Application):
    commands = [
        BotCommand("start", "بدء البوت"),
        BotCommand("cancel", "إلغاء العملية"),
        BotCommand("help", "عرض المساعدة"),
    ]
    await application.bot.set_my_commands(commands)
    print("✅ تم إعداد الأوامر")

def main():
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
        print("📁 تم إنشاء مجلد التحميلات")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.post_init = post_init
    
    print("=" * 50)
    print("🚀 البوت يعمل الآن!")
    print("=" * 50)
    print(f"✅ المنصات: {len(PLATFORMS)}")
    print(f"🎬 {', '.join(PLATFORMS.keys())}")
    print("=" * 50)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
