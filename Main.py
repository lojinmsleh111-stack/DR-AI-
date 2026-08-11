import discord
from discord.ext import commands
import os
import logging
from keep_alive import keep_alive

TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("DISCORD_TOKEN")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("bot")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# قائمة الملفات المفصولة داخل مجلد cogs المراد تحميلها
INITIAL_EXTENSIONS = [
    "cogs.tickets",
    "cogs.apply",
    "cogs.streak",
]

@bot.event
async def on_ready():
    # تحميل كل ميزة من ملفها المخصص
    for ext in INITIAL_EXTENSIONS:
        try:
            await bot.load_extension(ext)
            logger.info(f"✅ تم تحميل الميزة: {ext}")
        except Exception as e:
            logger.error(f"❌ فشل تحميل الميزة {ext}: {e}")

    # مزامنة أوامر السلاش
    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ تم مزامنة {len(synced)} أمر سلاش بنجاح.")
    except Exception as e:
        logger.error(f"خطأ أثناء مزامنة أوامر السلاش: {e}")

    # حالة البوت
    await bot.change_presence(status=discord.Status.online, activity=discord.CustomActivity(name="Distributing"))
    logger.info(f"🚀 البوت جاهز ويعمل بنجاح باسم {bot.user}")

def run_bot():
    try:
        keep_alive()
    except Exception as e:
        logger.warning(f"تنبيه keep_alive: {e}")
        
    if not TOKEN:
        logger.error("❌ لم يتم العثور على توكن البوت في متغيرات البيئة!")
        return

    bot.run(TOKEN, log_handler=None)

if __name__ == "__main__": 
    run_bot()
    
