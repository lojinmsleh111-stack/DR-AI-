
import discord
from discord.ext import commands

# =========================
# IDs
# =========================

PANEL_CHANNEL_ID = 1543715791558414336

# رول أونري
OWNER_CHANNEL_ID = 1532414484151402586

# رول بلاي العادي
PLAY_CHANNEL_ID = 1532414474437394482

# روم الأكواد
CODE_CHANNEL_ID = 1532414489561927843

# الرتبة الموجودة في الرسائل
ROLE_ID = 1532414257772101812

# الرومات الموجودة داخل نص القوانين
NO_USE_CHANNEL_ID = 1532414397245296700
HOST_CHAT_CHANNEL_ID = 1532414490694385895
RULES_CHANNEL_ID = 1532414374789255419


# =========================
# الاختيار لكل مستخدم
# =========================

selected_roles = {}


# =========================
# View
# =========================

class GvView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    # =========================
    # رول أونري
    # =========================

    @discord.ui.button(
        label="رول اونر",
        style=discord.ButtonStyle.primary,
        custom_id="gv_owner"
    )
    async def owner_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        selected_roles[interaction.user.id] = "owner"

        await interaction.response.send_message(
            f"""# رول بـلاي 🎮

- الهوست: {interaction.user.mention}

- لي اضافه هوست توجه <#1532414489561927843>


- لي تصويت اضغط ✅

<@&1532414257772101812>""",
            ephemeral=False
        )

    # =========================
    # رول بلاي GV
    # =========================

    @discord.ui.button(
        label="رول بلاي GV",
        style=discord.ButtonStyle.primary,
        custom_id="gv_play"
    )
    async def play_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        selected_roles[interaction.user.id] = "play"

        await interaction.response.send_message(
            f"""# رول بـلاي 🎮

- الهوست: {interaction.user.mention}

- لي اضافه هوست توجه <#1532414489561927843>


- لي تصويت اضغط ✅

<@&1532414257772101812>""",
            ephemeral=False
        )

    # =========================
    # بداية الرول
    # =========================

    @discord.ui.button(
        label="بداية الرول",
        style=discord.ButtonStyle.success,
        custom_id="gv_start"
    )
    async def start_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        role = selected_roles.get(interaction.user.id)

        if role is None:
            await interaction.response.send_message(
                "❌ اختر رول أونر أو رول بلاي أولاً.",
                ephemeral=True
            )
            return

        if role == "owner":
            channel_id = OWNER_CHANNEL_ID
        else:
            channel_id = PLAY_CHANNEL_ID

        channel = interaction.guild.get_channel(channel_id)

        if channel is None:
            await interaction.response.send_message(
                "❌ ما قدرت ألقى روم الرول.",
                ephemeral=True
            )
            return

        message = f"""# قـوانـيـن رول بـلاي 

- بـسم الله الرحمن الرحيم توكلنا على الله 


- الهوست: {interaction.user.mention}

- سرعه المسار الايمن 60 والايسر 65

- ممنوع الهروب من الاداره والهوست

- احترام قرارات هوست والاداره 

- تخريبك يؤدي لعقوبتك

- ممنوع استخدام  <#1532414397245296700> 

- ممنوع وضع لوحات مميزه بدون تصريح

- تواصل داخل رومين <#1532414490694385895> ورم صوتي

- الاداره تتمنى لكم رول جميل وهادئ

<@&1532414257772101812>

<#1532414374789255419>"""

        await channel.send(message)

        await interaction.response.send_message(
            "✅ تم إرسال بداية الرول في الروم الصحيح.",
            ephemeral=True
        )

    # =========================
    # قفلت الرول
    # =========================

    @discord.ui.button(
        label="قفلت الرول",
        style=discord.ButtonStyle.danger,
        custom_id="gv_close"
    )
    async def close_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        role = selected_roles.get(interaction.user.id)

        if role is None:
            await interaction.response.send_message(
                "❌ اختر رول أونر أو رول بلاي أولاً.",
                ephemeral=True
            )
            return

        # حذف رسائل البوت القديمة من رومات الرول
        for channel_id in [OWNER_CHANNEL_ID, PLAY_CHANNEL_ID]:
            channel = interaction.guild.get_channel(channel_id)

            if channel is None:
                continue

            try:
                async for message in channel.history(limit=100):
                    if message.author == interaction.client.user:
                        try:
                            await message.delete()
                        except:
                            pass
            except:
                pass

        if role == "owner":
            channel_id = OWNER_CHANNEL_ID
        else:
            channel_id = PLAY_CHANNEL_ID

        channel = interaction.guild.get_channel(channel_id)

        if channel is None:
            await interaction.response.send_message(
                "❌ ما قدرت ألقى روم الرول.",
                ephemeral=True
            )
            return

        # التقييم - نفس الكلام الأصلي
        evaluation = f"""# تقييم رول 🎮

- الهوست: {interaction.user.mention}

- اذا عجبك ✅ إذا لا ❌ ذكر سبب بشات العام 

- ملاحظه 🔴

- اذا متبلك ممنوع تصوت في حال تصويتك يحق للهوست رفع تذكره وتتم معاقبتك

<@&1532414257772101812>"""

        evaluation_message = await channel.send(evaluation)

        # إضافة الإيموجيات تلقائيًا
        try:
            await evaluation_message.add_reaction("✅")
            await evaluation_message.add_reaction("❌")
        except:
            pass

        await interaction.response.send_message(
            "✅ تم قفل الرول وإرسال التقييم.",
            ephemeral=True
        )

    # =========================
    # إرسال الكود
    # =========================

    @discord.ui.button(
        label="إرسال الكود",
        style=discord.ButtonStyle.secondary,
        custom_id="gv_code"
    )
    async def code_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        class CodeModal(discord.ui.Modal, title="إرسال الكود"):

            code = discord.ui.TextInput(
                label="الكود",
                placeholder="اكتب الكود هنا",
                required=True
            )

            async def on_submit(
                self,
                modal_interaction: discord.Interaction
            ):
                channel = modal_interaction.guild.get_channel(
                    CODE_CHANNEL_ID
                )

                if channel is None:
                    await modal_interaction.response.send_message(
                        "❌ ما قدرت ألقى روم الأكواد.",
                        ephemeral=True
                    )
                    return

                await channel.send(
                    f"""# كود الرول حاليا هو : 




{self.code.value}




# يرجى كتابة اسمك أدناه لتتجنب البلوك !"""
                )

                await modal_interaction.response.send_message(
                    "✅ تم إرسال الكود.",
                    ephemeral=True
                )

        await interaction.response.send_modal(CodeModal())


# =========================
# Cog
# =========================

class GvRoles(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):

        self.bot.add_view(GvView())

        channel = self.bot.get_channel(PANEL_CHANNEL_ID)

        if channel is None:
            print("❌ PANEL CHANNEL NOT FOUND")
            return

        print("✅ GV ROLES READY")


async def setup(bot):
    await bot.add_cog(GvRoles(bot))
