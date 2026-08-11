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

# استيراد الـ View الدائم الخاص بالتصريح
from cogs.apply import ApplyStartView

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # تسجيل الأزرار الدائمة حتى تعمل مباشرة بعد إعادة التشغيل
        self.add_view(ApplyStartView())
        
        # تحميل جميع الأكواد (Cogs)
        initial_extensions = [
            "cogs.apply",
            "cogs.streak",
            "cogs.tickets"
        ]
        
        for ext in initial_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"✅ تم تحميل الميزة: {ext}")
            except Exception as e:
                logger.error(f"❌ فشل تحميل الميزة {ext}: {e}")

    async def on_ready(self):
        logger.info(f"🚀 DR | البوت جاهز ويعمل بنجاح باسم {self.user}")

bot = MyBot()

# تشغيل البوت باستخدام التوكن من متغيرات البيئة
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        logger.error("❌ لم يتم العثور على توكن البوت في متغيرات البيئة (DISCORD_TOKEN / TOKEN)!")
        
