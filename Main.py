from keep_alive import keep_alive

keep_alive()

import discord
from discord.ext import commands
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class MyBot(commands.Bot):

    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents
        )

    async def setup_hook(self):

        initial_extensions = [
    "cogs.apply",
    "cogs.streak",
    "cogs.tickets",
    "cogs.support_tickets",
    
        ]

        for ext in initial_extensions:

            try:

                await self.load_extension(ext)

                logger.info(
                    f"✅ تم تحميل: {ext}"
                )

            except Exception as e:

                logger.error(
                    f"❌ فشل تحميل {ext}: {e}",
                    exc_info=True
                )

        # مزامنة أوامر Slash
        try:

            synced = await self.tree.sync()

            logger.info(
                f"✅ تم مزامنة {len(synced)} أمر Slash"
            )

        except Exception as e:

            logger.error(
                f"❌ فشل مزامنة أوامر Slash: {e}",
                exc_info=True
            )


bot = MyBot()


@bot.event
async def on_ready():

    logger.info(
        f"✅ تم تسجيل الدخول باسم "
        f"{bot.user} (ID: {bot.user.id})"
    )


bot.run(
    os.getenv("DISCORD_TOKEN")
)
