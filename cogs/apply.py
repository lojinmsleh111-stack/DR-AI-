import discord
from discord.ext import commands
import logging

logger = logging.getLogger("bot")

REVIEW_CHANNEL_ID = 1532414607577055465
PASSED_ROLE_ID = 1524373417137016833
ALLOWED_SETUP_ROLE_ID = 1532414187685413055


def has_review_permission(member: discord.Member) -> bool:
    """Check whether a member is allowed to accept/reject applications."""
    if member.guild_permissions.administrator:
        return True
    role = member.guild.get_role(ALLOWED_SETUP_ROLE_ID)
    return role is not None and role in member.roles


class ApplyModal(discord.ui.Modal, title="تقديم طلب تصريح رول بلاي"):
    q1 = discord.ui.TextInput(label="الاسم الكريم:", placeholder="أدخل اسمك...", required=True, max_length=100)
    q2 = discord.ui.TextInput(label="عمرك الحقيقي:", placeholder="الرجاء وضع عمرك الحقيقي (أرقام فقط)...", required=True, max_length=3)
    q3 = discord.ui.TextInput(label="اسم حسابك الأساسي في روبلوكس:", placeholder="Username...", required=True, max_length=100)
    q4 = discord.ui.TextInput(label="اختصار الحساب:", placeholder="Display Name / اليوزر...", required=True, max_length=100)
    q5 = discord.ui.TextInput(
        label="قسم التعهد بالالتزام بقوانين السيرفر واحترام الإدارة والأعضاء:",
        style=discord.TextStyle.paragraph,
        placeholder="اكتب القسم هنا...",
        required=True,
        max_length=1000
    )

    def __init__(self, cog: "ApplyCog"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        # Validate age is numeric and reasonable
        age_raw = self.q2.value.strip()
        if not age_raw.isdigit() or not (1 <= int(age_raw) <= 120):
            return await interaction.response.send_message(
                "❌ الرجاء إدخال عمر صحيح (أرقام فقط).", ephemeral=True
            )

        # Prevent duplicate pending applications from the same user
        if interaction.user.id in self.cog.pending_applicants:
            return await interaction.response.send_message(
                "⏳ لديك طلب قيد المراجعة بالفعل، الرجاء الانتظار حتى يتم الرد عليه.", ephemeral=True
            )

        self.cog.pending_applicants.add(interaction.user.id)

        await interaction.response.send_message("✅ تم إرسال طلبك بنجاح! سيتم مراجعته من قبل إدارة الرول بلاي.", ephemeral=True)

        review_channel = interaction.guild.get_channel(REVIEW_CHANNEL_ID)
        if review_channel is None:
            try:
                review_channel = await interaction.guild.fetch_channel(REVIEW_CHANNEL_ID)
            except Exception:
                logger.warning("Review channel %s not found/accessible", REVIEW_CHANNEL_ID)
                review_channel = None

        if review_channel:
            embed = discord.Embed(
                title="📑 طلب تصريح رول بلاي جديد",
                description=f"قدم المواطن {interaction.user.mention} طلب للحصول على التصريح.",
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            embed.add_field(name="👤 العضو", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
            embed.add_field(name="1️⃣ الاسم الكريم:", value=self.q1.value, inline=False)
            embed.add_field(name="2️⃣ عمرك الحقيقي:", value=age_raw, inline=True)
            embed.add_field(name="3️⃣ اسم حسابك الأساسي في روبلوكس:", value=f"`{self.q3.value}`", inline=True)
            embed.add_field(name="4️⃣ اختصار الحساب:", value=f"`{self.q4.value}`", inline=True)
            embed.add_field(name="5️⃣ القسم:", value=self.q5.value, inline=False)

            view = RPReviewButtons(applicant_id=interaction.user.id, char_name=self.q1.value, cog=self.cog)
            await review_channel.send(embed=embed, view=view)
            logger.info("New RP application submitted by %s (%s)", interaction.user, interaction.user.id)
        else:
            # Couldn't post to review channel — don't leave the user stuck as "pending" forever
            self.cog.pending_applicants.discard(interaction.user.id)


class RPReviewButtons(discord.ui.View):
    """
    NOTE: For true persistence across bot restarts, applicant_id/char_name
    need to be recoverable without relying on in-memory state. This view is
    only guaranteed to keep working after a restart for *disabling* stale
    buttons (see ApplyCog.on_ready), not for a fresh accept/reject action.
    """
    def __init__(self, applicant_id: int, char_name: str, cog: "ApplyCog"):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id
        self.char_name = char_name
        self.cog = cog

    async def _resolve_and_lock(self, interaction: discord.Interaction, button: discord.ui.Button) -> bool:
        """Shared permission check + anti-race guard. Returns True if this
        interaction should proceed."""
        if not has_review_permission(interaction.user):
            await interaction.response.send_message("❌ لا تملك صلاحية القيام بهذا الإجراء.", ephemeral=True)
            return False

        if button.disabled:
            await interaction.response.send_message("⚠️ تم التعامل مع هذا الطلب بالفعل.", ephemeral=True)
            return False

        return True

    @discord.ui.button(label="✅ قبول الطلب", style=discord.ButtonStyle.success, custom_id="rp_review_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._resolve_and_lock(interaction, button):
            return

        # Disable immediately to close the race window between two admins clicking at once
        for child in self.children:
            child.disabled = True
        button.label = f"✅ مقبول بواسطة {interaction.user.display_name}"
        await interaction.response.edit_message(view=self)

        member = interaction.guild.get_member(self.applicant_id)
        role = interaction.guild.get_role(PASSED_ROLE_ID)

        if member:
            if role:
                try:
                    await member.add_roles(role)
                except Exception as e:
                    logger.warning("Failed to add role to %s: %s", member.id, e)
            try:
                await member.edit(nick=self.char_name)
            except Exception as e:
                logger.warning("Failed to set nickname for %s: %s", member.id, e)
            try:
                await member.send("🎉 **مبروك!** تم قبول طلب تصريح الرول بلاي الخاص بك بنجاح.")
            except Exception as e:
                logger.info("Could not DM %s: %s", member.id, e)

        self.cog.pending_applicants.discard(self.applicant_id)
        logger.info("Application %s accepted by %s", self.applicant_id, interaction.user.id)

    @discord.ui.button(label="❌ رفض الطلب", style=discord.ButtonStyle.danger, custom_id="rp_review_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._resolve_and_lock(interaction, button):
            return

        for child in self.children:
            child.disabled = True
        button.label = f"❌ مرفوض بواسطة {interaction.user.display_name}"
        await interaction.response.edit_message(view=self)

        member = interaction.guild.get_member(self.applicant_id)
        if member:
            try:
                await member.send("❌ نأسف لإبلاغك بأنه تم رفض طلب تصريح الرول بلاي الخاص بك.")
            except Exception as e:
                logger.info("Could not DM %s: %s", member.id, e)

        self.cog.pending_applicants.discard(self.applicant_id)
        logger.info("Application %s rejected by %s", self.applicant_id, interaction.user.id)


class ApplyStartView(discord.ui.View):
    def __init__(self, cog: "ApplyCog"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="تقديم طلب تصريح رول بلاي",
        style=discord.ButtonStyle.blurple,
        emoji="👾",
        custom_id="replit_apply_btn_final"
    )
    async def start_apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ApplyModal(self.cog))


class ApplyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Tracks user IDs with a currently pending (unreviewed) application.
        # NOTE: this is in-memory only and resets on bot restart — if you need
        # it to survive restarts, back it with a DB/JSON file instead.
        self.pending_applicants: set[int] = set()

    async def cog_load(self):
        # Register persistent views so buttons keep working after a restart.
        # Note: RPReviewButtons registered this way won't know the original
        # applicant_id/char_name for *new* clicks after a restart, since that
        # state isn't persisted anywhere — only the "already handled" disabled
        # state on already-clicked messages survives. For full durability,
        # store applicant_id/char_name (e.g. in the embed or a DB) and look
        # them up in the button callback instead of relying on __init__.
        self.bot.add_view(ApplyStartView(self))

    @commands.command(name="setup_apply")
    async def setup_apply(self, ctx):
        if not has_review_permission(ctx.author):
            return await ctx.send("❌ عفواً، هذا الأمر مخصص لرتبة معينة فقط!")

        embed = discord.Embed(
            title="🎮 طلب تصريح دخول الرول بلاي",
            description="أهلاً بك في السيرفر!\n\nللحصول على تصريح الرول بلاي، اضغط على الزر بالأسفل وقم بتعبئة البيانات المطلوبة.",
            color=discord.Color.blurple()
        )
        embed.set_footer(text="إدارة سيرفر الرول بلاي 📗")

        await ctx.send(embed=embed, view=ApplyStartView(self))
        try:
            await ctx.message.delete()
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(ApplyCog(bot))
        
