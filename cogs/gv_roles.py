import discord
from discord.ext import commands


# =========================================================
# CHANNELS / ROLES / SETTINGS
# =========================================================

# روم الـ Panel
PANEL_CHANNEL_ID = 1543715791558414336

# روم رول أونري
OWNER_CHANNEL_ID = 1543715737040855091

# رومات رول بلاي GV العادي
PLAY_CHANNEL_IDS = (
    1532414484151402586,
    1532414474437394482,
)

# روم إرسال كود الرول
CODE_CHANNEL_ID = 1532414489561927843

# روم القوانين
RULES_CHANNEL_ID = 1458141125461147791

# الرتب
GV_NOTIFY_ROLE_ID = 1532414257772101812

# الرتب المستخدمة في رسالة الرول
OWNER_ROLE_ID = 0
GV_ROLE_ID = 0

# =========================================================
# OTHER CHANNELS
# =========================================================

VOICE_RULE_CHANNEL_ID = 1532414490694385895
HOST_CHANNEL_ID = 1532414489561927843
NO_USE_CHANNEL_ID = 1532414397245296700
FINAL_RULES_CHANNEL_ID = 1532414374789255419

# =========================================================
# EMOJIS
# =========================================================

# استخدمنا إيموجي عادي حتى لا تحتاج IDs من ملف config
GV_EMOJI = "🎮"
YES_EMOJI = "✅"
NO_EMOJI = "❌"


# =========================================================
# حفظ اختيار العضو
# =========================================================

selected_roles = {}


# =========================================================
# VIEW
# =========================================================

class GvView(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def send_to_channels(
        self,
        interaction: discord.Interaction,
        channel_ids,
        content
    ):
        sent = []

        for channel_id in channel_ids:

            channel = interaction.guild.get_channel(channel_id)

            if not channel:
                continue

            try:
                await channel.send(content)
                sent.append(channel)

            except discord.HTTPException:
                pass

        return sent

    # =====================================================
    # رول أونري
    # =====================================================

    @discord.ui.button(
        label="رول اونر",
        style=discord.ButtonStyle.primary,
        custom_id="gv_owner"
    )
    async def owner(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        selected_roles[interaction.user.id] = "owner"

        text = (
            "**__ رول بلاي اونري\n\n"
            f"- رول بلاي اونري {GV_EMOJI}\n\n"
            f"- صاحب الرول : {interaction.user.mention}\n\n"
            "`في حال عدم تصويتك للرول وتخش الرول سيتم معاقبتك`\n\n"
            "`يرجى مراجعة القوانين قبل دخولك للرول لتفادي العواقب`\n\n"
            f"<@&{OWNER_ROLE_ID}>\n\n"
            f"<@&{GV_ROLE_ID}>\n\n"
            "..\n"
            "__**"
        )

        await self.send_to_channels(
            interaction,
            (OWNER_CHANNEL_ID,),
            text
        )

        await interaction.response.send_message(
            "تم إرسال نموذج رول اونري.",
            ephemeral=True
        )

    # =====================================================
    # رول بلاي GV
    # =====================================================

    @discord.ui.button(
        label="رول بلاي GV",
        style=discord.ButtonStyle.primary,
        custom_id="gv_play"
    )
    async def play(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        selected_roles[interaction.user.id] = "play"

        text = (
            "**__ رول بلاي Gv\n\n"
            f"رول بلاي جرينفل {GV_EMOJI}\n\n"
            f"صاحب الرول : {interaction.user.mention}\n\n"
            "`في حال عدم تصويتك للرول وتخش الرول سيتم معاقبتك`\n\n"
            "`يرجى مراجعة القوانين قبل دخولك للرول لتفادي العواقب`\n\n"
            f"<@&{OWNER_ROLE_ID}>\n\n"
            f"<@&{GV_ROLE_ID}>\n\n"
            "..\n\n"
            "__**"
        )

        # يرسل في نفس رومات رول بلاي GV
        await self.send_to_channels(
            interaction,
            PLAY_CHANNEL_IDS,
            text
        )

        await interaction.response.send_message(
            "تم إرسال نموذج رول بلاي GV.",
            ephemeral=True
        )

    # =====================================================
    # بداية الرول
    # =====================================================

    @discord.ui.button(
        label="بداية الرول",
        style=discord.ButtonStyle.success,
        custom_id="gv_start"
    )
    async def start(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        selected_role = selected_roles.get(
            interaction.user.id
        )

        # ---------------------------------------------
        # أونري
        # ---------------------------------------------

        if selected_role == "owner":

            target_channels = (
                OWNER_CHANNEL_ID,
            )

        # ---------------------------------------------
        # GV عادي
        # ---------------------------------------------

        elif selected_role == "play":

            target_channels = PLAY_CHANNEL_IDS

        else:

            await interaction.response.send_message(
                "اختر رول أونري أو رول بلاي GV أولاً.",
                ephemeral=True
            )
            return

        # ---------------------------------------------
        # رسالة بداية الرول
        # ---------------------------------------------

        text = (
            "# قـوانـيـن رول بـلاي\n\n"
            "- بـسم الله الرحمن الرحيم توكلنا على الله\n\n"
            f"- الهوست: {interaction.user.mention}\n\n"
            "- سرعه المسار الايمن 60 والايسر 65\n\n"
            "- ممنوع الهروب من الاداره والهوست\n\n"
            "- احترام قرارات هوست والاداره\n\n"
            "- تخريبك يؤدي لعقوبتك\n\n"
            f"- ممنوع استخدام <#{NO_USE_CHANNEL_ID}>\n\n"
            "- ممنوع وضع لوحات مميزه بدون تصريح\n\n"
            f"- تواصل داخل رومين <#{VOICE_RULE_CHANNEL_ID}> ورم صوتي\n\n"
            "- الاداره تتمنى لكم رول جميل وهادئ\n\n"
            f"<@&{GV_NOTIFY_ROLE_ID}>\n\n"
            f"<#{FINAL_RULES_CHANNEL_ID}>"
        )

        await self.send_to_channels(
            interaction,
            target_channels,
            text
        )

        await interaction.response.send_message(
            "تم إرسال بداية الرول.",
            ephemeral=True
        )

    # =====================================================
    # التقييم
    # =====================================================

    @discord.ui.button(
        label="تقييم الرول",
        style=discord.ButtonStyle.secondary,
        custom_id="gv_rating"
    )
    async def rating(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        selected_role = selected_roles.get(
            interaction.user.id
        )

        if selected_role == "owner":

            target_channels = (
                OWNER_CHANNEL_ID,
            )

        elif selected_role == "play":

            target_channels = PLAY_CHANNEL_IDS

        else:

            await interaction.response.send_message(
                "اختر رول أونري أو رول بلاي GV أولاً.",
                ephemeral=True
            )
            return

        text = (
            "# تقييم رول 🎮\n\n"
            f"- الهوست: {interaction.user.mention}\n\n"
            "- اذا عجبك ✅ إذا لا ❌ ذكر سبب بشات العام\n\n"
            "- ملاحظه 🔴\n\n"
            "- اذا متبلك ممنوع تصوت في حال تصويتك "
            "يحق للهوست رفع تذكره وتتم معاقبتك\n\n"
            f"<@&{GV_NOTIFY_ROLE_ID}>"
        )

        for channel_id in target_channels:

            channel = interaction.guild.get_channel(
                channel_id
            )

            if not channel:
                continue

            try:

                message = await channel.send(text)

                # البوت يحط الصح والخطأ بنفسه
                await message.add_reaction(YES_EMOJI)
                await message.add_reaction(NO_EMOJI)

            except discord.HTTPException:
                pass

        await interaction.response.send_message(
            "تم إرسال التقييم وإضافة ✅ و ❌.",
            ephemeral=True
        )

    # =====================================================
    # قفلت الرول
    # =====================================================

    @discord.ui.button(
        label="قفلت الرول",
        style=discord.ButtonStyle.danger,
        custom_id="gv_close"
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        channels = (
            OWNER_CHANNEL_ID,
            *PLAY_CHANNEL_IDS
        )

        for channel_id in channels:

            channel = interaction.guild.get_channel(
                channel_id
            )

            if not channel:
                continue

            try:

                async for message in channel.history(
                    limit=100
                ):

                    if message.author.id == self.bot.user.id:

                        await message.delete()

            except discord.HTTPException:
                pass

        await interaction.response.send_message(
            "تم إغلاق الرول وحذف رسائل البوت المطلوبة.",
            ephemeral=True
        )

    # =====================================================
    # إرسال الكود
    # =====================================================

    @discord.ui.button(
        label="إرسال الكود",
        style=discord.ButtonStyle.secondary,
        custom_id="gv_code"
    )
    async def code(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_modal(
            CodeModal()
        )


# =========================================================
# CODE MODAL
# =========================================================

class CodeModal(
    discord.ui.Modal,
    title="إرسال الكود"
):

    code = discord.ui.TextInput(
        label="الكود",
        placeholder="اكتب الكود هنا",
        required=True,
        max_length=100
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        channel = interaction.guild.get_channel(
            CODE_CHANNEL_ID
        )

        if channel:

            await channel.send(
                "# كود الرول حاليا هو :\n\n"
                f"`{self.code.value}`\n\n"
                "# يرجى كتابة اسمك أدناه لتتجنب البلوك !"
            )

        await interaction.response.send_message(
            "تم إرسال الكود.",
            ephemeral=True
        )


# =========================================================
# COG
# =========================================================

class GvRoles(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):

        channel = self.bot.get_channel(
            PANEL_CHANNEL_ID
        )

        if not channel:
            return

        found = False

        try:

            async for message in channel.history(
                limit=100
            ):

                if (
                    message.author.id == self.bot.user.id
                    and message.components
                ):
                    found = True
                    break

        except discord.HTTPException:
            return

        if not found:

            embed = discord.Embed(
                title="رول gv"
            )

            await channel.send(
                embed=embed,
                view=GvView(self.bot)
            )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    bot.add_view(
        GvView(bot)
    )

    await bot.add_cog(
        GvRoles(bot)
        )
