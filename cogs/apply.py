import discord
from discord.ext import commands
import logging

logger = logging.getLogger("bot")

REVIEW_CHANNEL_ID = 1532414607577055465
PASSED_ROLE_ID = 1524373417137016833
ALLOWED_SETUP_ROLE_ID = 1532414187685413055


class ApplyModal(discord.ui.Modal, title="تقديم طلب تصريح رول بلاي"):
    q1 = discord.ui.TextInput(
        label="الاسم الكريم:",
        placeholder="أدخل اسمك...",
        required=True,
        max_length=100
    )
    q2 = discord.ui.TextInput(
        label="عمرك الحقيقي:",
        placeholder="الرجاء وضع عمرك الحقيقي...",
        required=True,
        max_length=10
    )
    q3 = discord.ui.TextInput(
        label="اسم حسابك الأساسي في روبلوكس:",
        placeholder="Username...",
        required=True,
        max_length=100
    )
    q4 = discord.ui.TextInput(
        label="اختصار الحساب:",
        placeholder="Display Name / اليوزر...",
        required=True,
        max_length=100
    )
    q5 = discord.ui.TextInput(
        label="قسم التعهد بالالتزام بقوانين السيرفر واحترام الإدارة والأعضاء:",
        style=discord.TextStyle.paragraph,
        placeholder="اكتب القسم هنا...",
        required=True,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ تم إرسال طلبك بنجاح! سيتم مراجعته من قبل إدارة الرول بلاي.", ephemeral=True)

        review_channel = interaction.guild.get_channel(REVIEW_CHANNEL_ID)
        if review_channel:
            embed = discord.Embed(
                title="📑 طلب تصريح رول بلاي جديد",
                description=f"قدم المواطن {interaction.user.mention} طلب للحصول على التصريح.",
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            embed.add_field(name="👤 العضو", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
            embed.add_field(name="1️⃣ الاسم الكريم:", value=self.q1.value, inline=False)
            embed.add_field(name="2️⃣ عمرك الحقيقي:", value=self.q2.value, inline=True)
            embed.add_field(name="3️⃣ اسم حسابك الأساسي في روبلوكس:", value=f"`{self.q3.value}`", inline=True)
            embed.add_field(name="4️⃣ اختصار الحساب:", value=f"`{self.q4.value}`", inline=True)
            embed.add_field(name="5️⃣ قسم التعهد بالالتزام بقوانين السيرفر واحترام الإدارة والأعضاء:", value=self.q5.value, inline=False)
            embed.set_footer(text="استخدم الأزرار بالأسفل قبول أو رفض الطلب")

            view = RPReviewButtons(applicant_id=interaction.user.id, char_name=self.q1.value)
            await review_channel.send(embed=embed, view=view)


class RPReviewButtons(discord.ui.View):
    def __init__(self, applicant_id: int, char_name: str):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id
        self.char_name = char_name

    @discord.ui.button(label="✅ قبول الطلب", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        target_role = interaction.guild.get_role(ALLOWED_SETUP_ROLE_ID)
        if target_role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ لا تملك صلاحية قبول الطلبات.", ephemeral=True)

        member = interaction.guild.get_member(self.applicant_id)
        role = interaction.guild.get_role(PASSED_ROLE_ID)

        if member:
            if role:
                try:
                    await member.add_roles(role)
                except Exception as e:
                    logger.error(f"خطأ أثناء منح الرول: {e}")
            
            try:
                await member.edit(nick=self.char_name)
            except Exception:
                pass

            try:
                await member.send("🎉 **مبروك!** تم قبول طلب تصريح الرول بلاي الخاص بك بنجاح.")
            except Exception:
                pass

        for child in self.children:
            child.disabled = True
        button.label = f"✅ مقبول بواسطة {interaction.user.display_name}"
        
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"🟢 تم قبول طلب <@{self.applicant_id}> بنجاح!")

    @discord.ui.button(label="❌ رفض الطلب", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        target_role = interaction.guild.get_role(ALLOWED_SETUP_ROLE_ID)
        if target_role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ لا تملك صلاحية رفض الطلبات.", ephemeral=True)

        member = interaction.guild.get_member(self.applicant_id)
        if member:
            try:
                await member.send("❌ نأسف لإبلاغك بأنه تم رفض طلب تصريح الرول بلاي الخاص بك.")
            except Exception:
                pass

        for child in self.children:
            child.disabled = True
        button.label = f"❌ مرفوض بواسطة {interaction.user.display_name}"

        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"🔴 تم رفض طلب <@{self.applicant_id}>.")


class ApplyStartView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="تقديم طلب تصريح رول بلاي", 
        style=discord.ButtonStyle.blurple, 
        emoji="👾", 
        custom_id="persistent_rp_apply_button_v4"
    )
    async def start_apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ApplyModal())


class ApplyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setup_apply")
    async def setup_apply(self, ctx):
        required_role = ctx.guild.get_role(ALLOWED_SETUP_ROLE_ID)
        if required_role not in ctx.author.roles and not ctx.author.guild_permissions.administrator:
            return await ctx.send("❌ عفواً، هذا الأمر مخصص لرتبة معينة فقط!")

        embed = discord.Embed(
            title="🎮 طلب تصريح دخول الرول بلاي",
            description="أهلاً بك في السيرفر!\n\nللحصول على تصريح الرول بلاي، اضغط على الزر بالأسفل وقم بتعبئة البيانات المطلوبة.",
            color=discord.Color.blurple()
        )
        embed.set_footer(text="إدارة سيرفر الرول بلاي 📗")

        await ctx.send(embed=embed, view=ApplyStartView())
        try:
            await ctx.message.delete()
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(ApplyCog(bot))
    
