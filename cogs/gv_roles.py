import discord 
from discord.ext import commands

from utils.config import (
    GV_EMBED_CHANNELS,
    GV_OWNER_CHANNELS,
    GV_PLAY_CHANNELS,
    GV_START_CHANNELS,
    GV_EMOJI_ID,
    GV_PLAY_EMOJI_ID,
    GV_RULES_CHANNEL_ID,
    GV_EXTRA_RULES_CHANNEL_ID,
    GV_NOTIFY_ROLE_ID,
    OWNER_ROLE_ID,
    GV_ROLE_ID
)
PLAY_START_CHANNEL_ID = 


class GvView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.selected_roles = {}

    async def send_to_channels(self, interaction, channel_ids, content):
        sent = []

        for cid in channel_ids:
            channel = interaction.guild.get_channel(cid)

            if channel:
                try:
                    await channel.send(content)
                    sent.append(channel.mention)
                except discord.HTTPException:
                    pass

        return sent

    @discord.ui.button(
        label="رول اونر",
        style=discord.ButtonStyle.primary,
        custom_id="gv_owner"
    )
    async def owner(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.selected_roles[interaction.user.id] = "owner"

        emoji = f"<:gv:{GV_EMOJI_ID}>"

        rules_channel = interaction.guild.get_channel(GV_RULES_CHANNEL_ID)
        extra_rules_channel = interaction.guild.get_channel(GV_EXTRA_RULES_CHANNEL_ID)

        rules_mention = rules_channel.mention if rules_channel else ""
        extra_rules_mention = extra_rules_channel.mention if extra_rules_channel else ""

        text = (
            "**__ رول بلاي اونري\n\n"
            f"- رول بلاي اونري {emoji}\n\n"
            f"- صاحب الرول : {interaction.user.mention}\n\n"
            "` في حال عدم تصويتك للرول وتخش الرول سيتم معاقبتك `\n\n"
            "`يرجى مراجعة القوانين قبل دخولك للرول لتفادي العواقب`\n\n"
            f"{rules_mention}\n\n"
            f"{extra_rules_mention}\n\n"
            f"<@&{OWNER_ROLE_ID}>\n\n"
            f"<@&{GV_ROLE_ID}>\n\n"
            "..\n"
            "__**"
        )

        await self.send_to_channels(
            interaction,
            GV_OWNER_CHANNELS,
            text
        )

        await interaction.response.send_message(
            "تم إرسال نموذج رول اونر.",
            ephemeral=True
        )

    @discord.ui.button(
        label="رول بلاي GV",
        style=discord.ButtonStyle.primary,
        custom_id="gv_play"
    )
    async def play(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.selected_roles[interaction.user.id] = "play"

        emoji = f"<:gv:{GV_PLAY_EMOJI_ID}>"

        rules_channel = interaction.guild.get_channel(GV_RULES_CHANNEL_ID)
        extra_rules_channel = interaction.guild.get_channel(GV_EXTRA_RULES_CHANNEL_ID)

        rules_mention = rules_channel.mention if rules_channel else ""
        extra_rules_mention = extra_rules_channel.mention if extra_rules_channel else ""

        text = (
            "**__ رول بلاي Gv\n\n"
            f"رول بلاي جرينفل {emoji}\n\n"
            f"صاحب الرول : {interaction.user.mention}\n\n"
            "`في حال عدم تصويتك للرول وتخش الرول سيتم معاقبتك`\n\n"
            "`يرجى مراجعة القوانين قبل دخولك للرول لتفادي العواقب`\n\n"
            f"{rules_mention}\n\n"
            f"{extra_rules_mention}\n\n"
            f"<@&{OWNER_ROLE_ID}>\n\n"
            f"<@&{GV_ROLE_ID}>\n\n"
            "..\n\n"
            "__**"
        )

        await self.send_to_channels(
            interaction,
            GV_PLAY_CHANNELS,
            text
        )

        await interaction.response.send_message(
            "تم إرسال نموذج رول بلاي GV.",
            ephemeral=True
        )

    @discord.ui.button(
        label="بداية الرول",
        style=discord.ButtonStyle.success,
        custom_id="gv_start"
    )
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        selected_role = self.selected_roles.get(interaction.user.id)

        if selected_role == "owner":
            start_channel_id = OWNER_START_CHANNEL_ID

        elif selected_role == "play":
            start_channel_id = PLAY_START_CHANNEL_ID

        else:
            await interaction.response.send_message(
                "اختر رول أونري أو رول بلاي GV أولاً.",
                ephemeral=True
            )
            return

        text = (
            f"**__ بداية رولي ( {interaction.user.mention} )\n\n"
            "- رول بلاي gv\n\n"
            "- السرعه 70 ميل بالكيلو 110\n\n"
            "- تكتب اسمك هنا <#1458141125461147791> و تضيف الهوست\n\n"
            "- تخرب بلوك\n\n"
            f"|| <@&{GV_NOTIFY_ROLE_ID}> ||\n\n"
            "__**"
        )

        channel = interaction.guild.get_channel(start_channel_id)

        if channel:
            try:
                await channel.send(text)
            except discord.HTTPException:
                pass

        await interaction.response.send_message(
            "تم إرسال بداية الرول.",
            ephemeral=True
        )

    @discord.ui.button(
        label="قفلت الرول",
        style=discord.ButtonStyle.danger,
        custom_id="gv_close"
    )
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        for cid in (
            1458141719265542355,
            1458141041772204123
        ):
            channel = interaction.guild.get_channel(cid)

            if channel:
                try:
                    async for m in channel.history(limit=100):
                        if m.author.id == self.bot.user.id:
                            await m.delete()
                except discord.HTTPException:
                    pass

        await interaction.response.send_message(
            "تم إغلاق الرول وحذف رسائل البوت المطلوبة.",
            ephemeral=True
        )

    @discord.ui.button(
        label="إرسال الكود",
        style=discord.ButtonStyle.secondary,
        custom_id="gv_code"
    )
    async def code(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CodeModal())


class CodeModal(discord.ui.Modal, title="إرسال الكود"):
    code = discord.ui.TextInput(
        label="الكود",
        placeholder="اكتب الكود هنا",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(
            1458141125461147791
        )

        if channel:
            await channel.send(
                f"**__ الكود `{self.code.value}`\n\n"
                "ضروري ترسل يوزرك ولا راح ابندك ..\n\n"
                "@here\n\n"
                "__**"
            )

        await interaction.response.send_message(
            "تم إرسال الكود.",
            ephemeral=True
        )


class GvRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Send the persistent panel only if none from the bot exists
        # in the target channels.
        for cid in GV_EMBED_CHANNELS:
            channel = self.bot.get_channel(cid)

            if not channel:
                continue

            found = False

            try:
                async for m in channel.history(limit=100):
                    if (
                        m.author.id == self.bot.user.id
                        and m.embeds
                        and m.embeds[0].title == "رول gv"
                    ):
                        found = True
                        break

            except discord.HTTPException:
                continue

            if not found:
                embed = discord.Embed(title="رول gv")

                await channel.send(
                    embed=embed,
                    view=GvView(self.bot)
                )


async def setup(bot):
    bot.add_view(GvView(bot))
    await bot.add_cog(GvRoles(bot))
