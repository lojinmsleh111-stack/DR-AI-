from keep_alive import keep_alive
keep_alive()  # تشغيل السيرفر الوهمي لإرضاء Render
import discord
from discord.ext import commands
import os
import logging

# إعداد التسجيل (Logging)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

# تحديد الصلاحيات (Intents)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # تحميل جميع الأكواد (Cogs)
        # ApplyStartView يتسجل تلقائياً داخل cogs/apply.py عند تحميل الكوج
        initial_extensions = [
            "cogs.apply",
            "cogs.streak",
            "cogs.tickets"
        ]
        for ext in initial_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"✅ تم تحميل: {ext}")
            except Exception as e:
                logger.error(f"❌ فشل تحميل {ext}: {e}")

bot = MyBot()

@bot.event
async def on_ready():
    logger.info(f"✅ تم تسجيل الدخول باسم {bot.user} (ID: {bot.user.id})")

bot.run(os.getenv("DISCORD_TOKEN"))
