
import discord
from discord.ext import commands


# =========================================================
# CHANNEL IDS
# =========================================================

PANEL_CHANNEL_ID = 1543715791558414336

OWNER_CHANNEL_ID = 1532414484151402586

PLAY_CHANNEL_ID = 1532414474437394482

CODE_CHANNEL_ID = 1532414489561927843


# =========================================================
# OTHER IDS USED IN THE MESSAGES
# =========================================================

ROLE_ID = 1532414257772101812

NO_USE_CHANNEL_ID = 1532414397245296700

HOST_CHAT_CHANNEL_ID = 1532414490694385895

RULES_CHANNEL_ID = 1532414374789255419


# =========================================================
# USER ROLE SELECTION
# =========================================================

selected_roles = {}


# =========================================================
# GV VIEW
# =========================================================

class GvView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    # =====================================================
    # رول اونري
    # =====================================================

    @discord.ui.button(
        label="رول اونر",
        style=discord.ButtonStyle.primary,
        custom_id="gv_role_owner"
    )
    async def owner_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        selected_roles[interaction.user.id] = "owner"

        channel = interaction.guild.get_channel(
            OWNER_CHANNEL_ID
        )

        if channel is None:
            await interaction.response.send_message(
                "❌ روم رول أونري غير موجود.",
                ephemeral=True
            )
            return

        await channel.send(
            f"""# رول بـلاي 🎮

- الهوست: {interaction.user.mention}

- لي اضافه هوست توجه <#1532414489561927843>


- لي تصويت اضغط ✅

<@&1532414257772101812>"""
        )

        await interaction.response.send_message(
            "✅ تم إرسال الرول في روم رول أونري.",
            ephemeral=True
        )

    # =====================================================
    # رول بلاي GV
    # =====================================================

    @discord.ui.button(
        label="رول بلاي GV",
        style=discord.ButtonStyle.primary,
        custom_id="gv_role_play"
    )
    async def play_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        selected_roles[interaction.user.id] = "play"

        channel = interaction.guild.get_channel(
            PLAY_CHANNEL_ID
        )

        if channel is None:
            await interaction.response.send_message(
                "❌ روم رول بلاي غير موجود.",
                ephemeral=True
            )
            return

        await channel.send(
            f"""# رول بـلاي 🎮

- الهوست: {interaction.user.mention}

- لي اضافه هوست توجه <#1532414489561927843>


- لي تصويت اضغط ✅

<@&1532414257772101812>"""
        )

        await interaction.response.send_message(
            "✅ تم إرسال الرول في روم رول بلاي.",
            ephemeral=True
        )

    # =====================================================
    # بداية الرول
    # =====================================================

    @discord.ui.button(
        label="بداية الرول",
        style=discord.ButtonStyle.success,
        custom_id="gv_role_start"
    )
    async def start_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        selected_role = selected_roles.get(
            interaction.user.id
        )

        if selected_role is None:
            await interaction.response.send_message(
                "❌ اختر رول أونري أو رول بلاي أولاً.",
                ephemeral=True
            )
            return

        if selected_role == "owner":
            channel_id = OWNER_CHANNEL_ID
        else:
            channel_id = PLAY_CHANNEL_ID

        channel = interaction.guild.get_channel(
            channel_id
        )

        if channel is None:
            await interaction.response.send_message(
                "❌ روم الرول غير موجود.",
                ephemeral=True
            )
            return

        rules_message = f"""# قـوانـيـن رول بـلاي 

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

        await channel.send(rules_message)

        await interaction.response.send_message(
            "✅ تم إرسال بداية الرول.",
            ephemeral=True
        )

    # =====================================================
    # قفلت الرول
    # =====================================================

    @discord.ui.button(
        label="قفلت الرول",
        style=discord.ButtonStyle.danger,
        custom_id="gv_role_close"
    )
    async def close_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        selected_role = selected_roles.get(
            interaction.user.id
        )

        if selected_role is None:
            await interaction.response.send_message(
                "❌ اختر رول أونري أو رول بلاي أولاً.",
                ephemeral=True
            )
            return

        if selected_role == "owner":
            channel_id = OWNER_CHANNEL_ID
        else:
            channel_id = PLAY_CHANNEL_ID

        channel = interaction.guild.get_channel(
            channel_id
        )

        if channel is None:
            await interaction.response.send_message(
                "❌ روم الرول غير موجود.",
                ephemeral=True
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        evaluation_message = f"""# تقييم رول 🎮

- الهوست: {interaction.user.mention}

- اذا عجبك ✅ إذا لا ❌ ذكر سبب بشات العام 

- ملاحظه 🔴

- اذا متبلك ممنوع تصوت في حال تصويتك يحق للهوست رفع تذكره وتتم معاقبتك

<@&1532414257772101812>"""

        message = await channel.send(
            evaluation_message
        )

        # إضافة الإيموجيات تلقائيًا
        try:
            await message.add_reaction("✅")
            await message.add_reaction("❌")
        except discord.HTTPException:
            pass

        await interaction.followup.send(
            "✅ تم قفل الرول وإرسال التقييم.",
            ephemeral=True
        )

    # =====================================================
    # إرسال الكود
    # =====================================================

    @discord.ui.button(
        label="إرسال الكود",
        style=discord.ButtonStyle.secondary,
        custom_id="gv_role_code"
    )
    async def code_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        class CodeModal(
            discord.ui.Modal,
            title="إرسال الكود"
        ):

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
                        "❌ روم الأكواد غير موجود.",
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

        await interaction.response.send_modal(
            CodeModal()
        )


# =========================================================
# COG
# =========================================================

class GvRoles(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.view_added = False
        self.panel_checked = False

    # =====================================================
    # READY
    # =====================================================

    @commands.Cog.listener()
    async def on_ready(self):

        # تسجيل الأزرار مرة واحدة فقط
        if not self.view_added:
            self.bot.add_view(GvView())
            self.view_added = True

        # منع فحص/إرسال البانل كل مرة
        if self.panel_checked:
            return

        self.panel_checked = True

        channel = self.bot.get_channel(
            PANEL_CHANNEL_ID
        )

        if channel is None:
            print("❌ PANEL CHANNEL NOT FOUND")
            return

        # =================================================
        # البحث عن بانل موجود مسبقًا
        # =================================================

        async for message in channel.history(limit=100):

            if (
                message.author == self.bot.user
                and message.components
            ):
                for row in message.components:
                    for component in row.children:

                        if component.custom_id == "gv_role_owner":
                            print("✅ GV PANEL ALREADY EXISTS")
                            return

        # =================================================
        # إرسال بانل واحد فقط
        # =================================================

        embed = discord.Embed(
            title="رول بـلاي 🎮",
            description="اختار نوع الرول من الأزرار بالأسفل.",
            color=discord.Color.blue()
        )

        await channel.send(
            embed=embed,
            view=GvView()
        )

        print("✅ GV PANEL SENT")


# =========================================================
# SETUP
# =========================================================

async def setup(bot):
    await bot.add_cog(GvRoles(bot))
