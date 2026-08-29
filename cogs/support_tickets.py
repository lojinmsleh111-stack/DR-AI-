import discord
from discord.ext import commands
from discord import app_commands
import logging

logger = logging.getLogger("bot")

# =========================================================
# الإعدادات
# =========================================================

TICKET_PANEL_CHANNEL_ID = 1532414409303916655

STAFF_ROLE_IDS = {
    1532414218756686114,
    1532414202558283980,
}


# =========================================================
# الأدوات
# =========================================================

def is_staff(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True

    return any(role.id in STAFF_ROLE_IDS for role in member.roles)


def get_ticket_owner(channel: discord.TextChannel):
    if not channel.topic:
        return None

    if not channel.topic.startswith("ticket_owner:"):
        return None

    try:
        return int(channel.topic.split(":", 1)[1])
    except (ValueError, IndexError):
        return None


def is_ticket_channel(channel: discord.TextChannel) -> bool:
    return (
        isinstance(channel, discord.TextChannel)
        and (
            channel.name.startswith("ticket-")
            or channel.name.startswith("closed-ticket-")
        )
    )


# =========================================================
# زر إغلاق التكت
# =========================================================

class CloseTicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="إغلاق التكت",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="support_ticket_close"
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message(
                "❌ هذا الزر يعمل داخل التكت فقط.",
                ephemeral=True
            )

        if not is_ticket_channel(channel):
            return await interaction.response.send_message(
                "❌ هذا الروم ليس تكت.",
                ephemeral=True
            )

        owner_id = get_ticket_owner(channel)

        if not is_staff(interaction.user) and interaction.user.id != owner_id:
            return await interaction.response.send_message(
                "❌ ليس لديك صلاحية إغلاق هذا التكت.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "🔒 سيتم إغلاق التكت...",
            ephemeral=True
        )

        # منع الجميع من الكتابة
        try:
            owner = interaction.guild.get_member(owner_id) if owner_id else None

            if owner:
                await channel.set_permissions(
                    owner,
                    view_channel=True,
                    read_message_history=True,
                    send_messages=False
                )

            for role_id in STAFF_ROLE_IDS:
                role = interaction.guild.get_role(role_id)

                if role:
                    await channel.set_permissions(
                        role,
                        view_channel=True,
                        read_message_history=True,
                        send_messages=True
                    )

            await channel.edit(
                name=f"closed-{channel.name}"[:100]
            )

            embed = discord.Embed(
                title="🔒 تم إغلاق التكت",
                description=(
                    f"تم إغلاق التكت بواسطة {interaction.user.mention}.\n\n"
                    "يمكن للإدارة حذف التكت عند الحاجة."
                ),
                color=discord.Color.red()
            )

            await channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Ticket close error: {e}")


# =========================================================
# زر حذف التكت
# =========================================================

class DeleteTicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="حذف التكت",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
        custom_id="support_ticket_delete"
    )
    async def delete_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ هذا الزر مخصص للإدارة فقط.",
                ephemeral=True
            )

        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel):
            return

        if not channel.name.startswith("closed-"):
            return await interaction.response.send_message(
                "❌ يجب إغلاق التكت أولاً.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "🗑️ سيتم حذف التكت خلال 5 ثوانٍ...",
            ephemeral=True
        )

        await discord.utils.sleep_until(
            discord.utils.utcnow() + __import__("datetime").timedelta(seconds=5)
        )

        try:
            await channel.delete(
                reason=f"Ticket deleted by {interaction.user}"
            )
        except discord.Forbidden:
            pass


# =========================================================
# لوحة التحكم داخل التكت
# =========================================================

class TicketControlView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="استلام التكت",
        emoji="🙋",
        style=discord.ButtonStyle.success,
        custom_id="support_ticket_claim"
    )
    async def claim_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ هذا الزر مخصص للإدارة فقط.",
                ephemeral=True
            )

        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel):
            return

        button.disabled = True
        button.label = f"مستلم بواسطة {interaction.user.display_name}"

        embed = discord.Embed(
            title="🙋 تم استلام التكت",
            description=(
                f"تم استلام التكت بواسطة {interaction.user.mention}.\n"
                "سيتم متابعة طلبك من قبل الإدارة."
            ),
            color=discord.Color.green()
        )

        await interaction.response.edit_message(
            view=self
        )

        await channel.send(embed=embed)

    @discord.ui.button(
        label="إغلاق التكت",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="support_ticket_close_main"
    )
    async def close_main(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel):
            return

        owner_id = get_ticket_owner(channel)

        if not is_staff(interaction.user) and interaction.user.id != owner_id:
            return await interaction.response.send_message(
                "❌ ليس لديك صلاحية إغلاق هذا التكت.",
                ephemeral=True
            )

        owner = (
            interaction.guild.get_member(owner_id)
            if owner_id
            else None
        )

        if owner:
            await channel.set_permissions(
                owner,
                view_channel=True,
                read_message_history=True,
                send_messages=False
            )

        await channel.edit(
            name=f"closed-{channel.name}"[:100]
        )

        embed = discord.Embed(
            title="🔒 تم إغلاق التكت",
            description=(
                f"تم إغلاق التكت بواسطة {interaction.user.mention}.\n\n"
                "إذا كنت من الإدارة يمكنك حذف التكت من الزر بالأسفل."
            ),
            color=discord.Color.red()
        )

        await interaction.response.send_message(
            embed=embed,
            view=DeleteTicketView()
        )


# =========================================================
# اختيار نوع التكت
# =========================================================

class TicketTypeSelect(discord.ui.Select):

    def __init__(self):
        options = [

            discord.SelectOption(
                label="تذكرة إدارية",
                description="للاستفسارات والشكاوى والطلبات الإدارية",
                emoji="🛠️",
                value="admin"
            ),

            discord.SelectOption(
                label="الدعم الفني",
                description="للمشاكل والاستفسارات التقنية",
                emoji="🖥️",
                value="technical"
            ),

        ]

        super().__init__(
            placeholder="🎟️ اختر نوع التذكرة...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="support_ticket_type"
        )

    async def callback(self, interaction: discord.Interaction):

        guild = interaction.guild

        if guild is None:
            return await interaction.response.send_message(
                "❌ حدث خطأ.",
                ephemeral=True
            )

        panel_channel = guild.get_channel(TICKET_PANEL_CHANNEL_ID)

        if not isinstance(panel_channel, discord.TextChannel):
            return await interaction.response.send_message(
                "❌ لم يتم العثور على روم لوحة التكت.",
                ephemeral=True
            )

        # منع فتح أكثر من تكت
        for channel in guild.text_channels:

            if not is_ticket_channel(channel):
                continue

            owner_id = get_ticket_owner(channel)

            if owner_id == interaction.user.id:
                return await interaction.response.send_message(
                    f"❌ لديك تكت مفتوح بالفعل: {channel.mention}",
                    ephemeral=True
                )

        category = panel_channel.category

        if category is None:
            return await interaction.response.send_message(
                "❌ يجب أن تكون روم لوحة التكت داخل Category.",
                ephemeral=True
            )

        ticket_type = self.values[0]

        if ticket_type == "admin":
            ticket_name = f"ticket-admin-{interaction.user.name}"
            ticket_title = "🛠️ تذكرة إدارية"
            ticket_description = (
                "مرحباً بك في التذكرة الإدارية.\n\n"
                "يرجى توضيح طلبك أو شكواك بالتفصيل "
                "وإرفاق الدليل إذا كان مطلوباً."
            )

        else:
            ticket_name = f"ticket-support-{interaction.user.name}"
            ticket_title = "🖥️ تذكرة الدعم الفني"
            ticket_description = (
                "مرحباً بك في تذكرة الدعم الفني.\n\n"
                "يرجى شرح المشكلة بالتفصيل "
                "وإرفاق صورة أو دليل للمشكلة إن وجد."
            )

        # الصلاحيات
        overwrites = {

            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),

            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            ),

            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True,
                manage_permissions=True,
                attach_files=True,
                embed_links=True
            )

        }

        # إعطاء الرتبتين صلاحية التكت
        for role_id in STAFF_ROLE_IDS:

            role = guild.get_role(role_id)

            if role:

                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_messages=True,
                    attach_files=True,
                    embed_links=True
                )

        try:

            channel = await guild.create_text_channel(
                name=ticket_name[:100],
                category=category,
                overwrites=overwrites,
                topic=f"ticket_owner:{interaction.user.id}",
                reason=f"Ticket opened by {interaction.user}"
            )

        except discord.Forbidden:

            return await interaction.response.send_message(
                "❌ البوت لا يملك صلاحية إنشاء الرومات.",
                ephemeral=True
            )

        except Exception as e:

            logger.error(f"Ticket creation error: {e}")

            return await interaction.response.send_message(
                "❌ حدث خطأ أثناء إنشاء التكت.",
                ephemeral=True
            )

        embed = discord.Embed(
            title=ticket_title,
            description=ticket_description,
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="👤 صاحب التكت",
            value=interaction.user.mention,
            inline=True
        )

        embed.add_field(
            name="📌 النوع",
            value=(
                "🛠️ تذكرة إدارية"
                if ticket_type == "admin"
                else "🖥️ الدعم الفني"
            ),
            inline=True
        )

        embed.set_footer(
            text="يرجى الالتزام بقوانين التذاكر."
        )

        await channel.send(
            content=interaction.user.mention,
            embed=embed,
            view=TicketControlView()
        )

        await interaction.response.send_message(
            f"✅ تم فتح التكت بنجاح: {channel.mention}",
            ephemeral=True
        )


# =========================================================
# لوحة التكت
# =========================================================

class TicketPanelView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(TicketTypeSelect())


# =========================================================
# نظام التكت
# =========================================================

class SupportTickets(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    async def cog_load(self):

        # تسجيل الأزرار والقوائم بشكل دائم
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(TicketControlView())
        self.bot.add_view(DeleteTicketView())

    @app_commands.command(
        name="ticket_panel",
        description="إرسال لوحة نظام التذاكر"
    )
    async def ticket_panel(
        self,
        interaction: discord.Interaction
    ):

        if not is_staff(interaction.user):

            return await interaction.response.send_message(
                "❌ هذا الأمر مخصص للإدارة فقط.",
                ephemeral=True
            )

        if interaction.channel_id != TICKET_PANEL_CHANNEL_ID:

            return await interaction.response.send_message(
                f"❌ استخدم الأمر في <#{TICKET_PANEL_CHANNEL_ID}>.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="🎟️ نظام التذاكر",
            description=(َ
            ),
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="📜 قـوانـيـن التذكرة 🎟️",
            value=(
                "- ممنوع سب أو شتم اي شخص\n\n"
                "- احترام الجميع\n\n"
                "- ممنوع تفتح تكت بلا سبب\n\n"
                "- ما ترد بعد يوم كامل يتسكر التكت\n\n"
                "- اجباري إحضار دليل للمشكلة أو الشكوى\n\n"
                "- احترام قوانين الدعم الفني و الإدارة\n\n"
                "- ملاحظه🔴\n\n"
                "- جهلك بالقوانين لا يعفيك من العقوبة"
            ),
            inline=False
        )

        embed.set_footer(
            text="اختر نوع التذكرة المناسبة لك من القائمة."
        )

        await interaction.response.send_message(
            embed=embed,
            view=TicketPanelView()
        )


# =========================================================
# Setup
# =========================================================

async def setup(bot):
    await bot.add_cog(SupportTickets(bot))
