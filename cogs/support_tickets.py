import discord
from discord.ext import commands
from discord import app_commands
import asyncio
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
# Helpers
# =========================================================

def is_staff(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True

    return any(role.id in STAFF_ROLE_IDS for role in member.roles)


def get_panel_channel(guild: discord.Guild):
    channel = guild.get_channel(TICKET_PANEL_CHANNEL_ID)

    if isinstance(channel, discord.TextChannel):
        return channel

    return None


def is_ticket(channel) -> bool:
    if not isinstance(channel, discord.TextChannel):
        return False

    return channel.name.startswith(
        ("ticket-", "closed-ticket-", "closed-")
    )


def get_ticket_owner(channel):
    if not channel.topic:
        return None

    if not channel.topic.startswith("ticket_owner:"):
        return None

    try:
        return int(channel.topic.split(":", 1)[1])
    except (ValueError, IndexError):
        return None


# =========================================================
# لوحة اختيار نوع التكت
# =========================================================

class TicketPanelView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(TicketTypeSelect())


class TicketTypeSelect(discord.ui.Select):

    def __init__(self):

        options = [
            discord.SelectOption(
                label="تذكرة إدارية",
                description="فتح تذكرة للإدارة",
                emoji="🛠️",
                value="admin"
            ),
            discord.SelectOption(
                label="الدعم الفني",
                description="فتح تذكرة للدعم الفني",
                emoji="🖥️",
                value="technical"
            )
        ]

        super().__init__(
            placeholder="🎟️ اختر نوع التذكرة...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="support_ticket_type_select"
        )

    async def callback(self, interaction: discord.Interaction):

        guild = interaction.guild

        if guild is None:
            return await interaction.response.send_message(
                "❌ حدث خطأ.",
                ephemeral=True
            )

        panel_channel = get_panel_channel(guild)

        if panel_channel is None:
            return await interaction.response.send_message(
                "❌ لم يتم العثور على روم لوحة التكت.",
                ephemeral=True
            )

        # منع فتح أكثر من تكت
        for channel in guild.text_channels:

            if not is_ticket(channel):
                continue

            owner_id = get_ticket_owner(channel)

            if owner_id == interaction.user.id:
                return await interaction.response.send_message(
                    f"❌ عندك تكت مفتوح بالفعل: {channel.mention}",
                    ephemeral=True
                )

        # نفس Category الخاصة بلوحة التكت
        category = panel_channel.category

        if category is None:
            return await interaction.response.send_message(
                "❌ روم لوحة التكت يجب أن يكون داخل Category.",
                ephemeral=True
            )

        ticket_type = self.values[0]

        if ticket_type == "admin":
            channel_name = f"ticket-admin-{interaction.user.name}"
            ticket_title = "🛠️ التذكرة الإدارية"

        else:
            channel_name = f"ticket-support-{interaction.user.name}"
            ticket_title = "🖥️ تذكرة الدعم الفني"

        # =================================================
        # صلاحيات الروم
        # =================================================

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
                    manage_channels=True,
                    attach_files=True,
                    embed_links=True
                )

        try:

            channel = await guild.create_text_channel(
                name=channel_name[:100],
                category=category,
                overwrites=overwrites,
                topic=f"ticket_owner:{interaction.user.id}",
                reason=f"Ticket opened by {interaction.user}"
            )

        except discord.Forbidden:

            return await interaction.response.send_message(
                "❌ البوت لا يملك صلاحية إنشاء التكت.",
                ephemeral=True
            )

        except Exception as e:

            logger.error(
                f"Ticket creation error: {e}",
                exc_info=True
            )

            return await interaction.response.send_message(
                "❌ حدث خطأ أثناء إنشاء التكت.",
                ephemeral=True
            )

        # =================================================
        # رسالة التكت
        # =================================================

        embed = discord.Embed(
            title=ticket_title,
            description=(
                f"مرحباً {interaction.user.mention} 👋\n\n"
                "تم فتح التكت بنجاح.\n"
                "يرجى كتابة طلبك وانتظار الإدارة."
            ),
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="👤 صاحب التكت",
            value=interaction.user.mention,
            inline=True
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
# أزرار التكت
# =========================================================

class TicketControlView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    # -----------------------------------------------------
    # استلام
    # -----------------------------------------------------

    @discord.ui.button(
        label="استلام",
        emoji="🙋",
        style=discord.ButtonStyle.green,
        custom_id="support_ticket_claim"
    )
    async def claim(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not is_staff(interaction.user):

            return await interaction.response.send_message(
                "❌ الستاف فقط يستطيع استلام التكت.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="🙋 تم استلام التكت",
            description=(
                f"تم استلام التكت بواسطة "
                f"{interaction.user.mention}."
            ),
            color=discord.Color.green()
        )

        await interaction.response.send_message(
            embed=embed
        )

    # -----------------------------------------------------
    # إغلاق
    # -----------------------------------------------------

    @discord.ui.button(
        label="إغلاق",
        emoji="🔒",
        style=discord.ButtonStyle.gray,
        custom_id="support_ticket_close"
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not is_staff(interaction.user):

            return await interaction.response.send_message(
                "❌ الستاف فقط يستطيع إغلاق التكت.",
                ephemeral=True
            )

        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel):
            return

        owner_id = get_ticket_owner(channel)

        if owner_id:

            member = interaction.guild.get_member(owner_id)

            if member:

                try:

                    await channel.set_permissions(
                        member,
                        view_channel=True,
                        send_messages=False,
                        read_message_history=True
                    )

                except discord.Forbidden:
                    pass

        new_name = channel.name

        if not new_name.startswith("closed-"):
            new_name = f"closed-{new_name}"

        try:

            await channel.edit(
                name=new_name[:100]
            )

        except discord.Forbidden:

            return await interaction.response.send_message(
                "❌ البوت لا يملك صلاحية تغيير اسم التكت.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="🔒 تم إغلاق التكت",
            description=(
                f"تم إغلاق التكت بواسطة "
                f"{interaction.user.mention}.\n\n"
                "يمكن للإدارة حذفه عند الحاجة."
            ),
            color=discord.Color.red()
        )

        await interaction.response.send_message(
            embed=embed,
            view=ClosedTicketView()
        )

    # -----------------------------------------------------
    # حذف
    # -----------------------------------------------------

    @discord.ui.button(
        label="حذف",
        emoji="🗑️",
        style=discord.ButtonStyle.red,
        custom_id="support_ticket_delete"
    )
    async def delete(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not is_staff(interaction.user):

            return await interaction.response.send_message(
                "❌ الستاف فقط يستطيع حذف التكت.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "🗑️ سيتم حذف التكت خلال 5 ثوانٍ."
        )

        await asyncio.sleep(5)

        try:
            await interaction.channel.delete()

        except discord.Forbidden:
            pass


# =========================================================
# أزرار التكت بعد الإغلاق
# =========================================================

class ClosedTicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="حذف التكت",
        emoji="🗑️",
        style=discord.ButtonStyle.red,
        custom_id="support_closed_ticket_delete"
    )
    async def delete(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not is_staff(interaction.user):

            return await interaction.response.send_message(
                "❌ هذا الزر للإدارة فقط.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "🗑️ سيتم حذف التكت خلال 5 ثوانٍ."
        )

        await asyncio.sleep(5)

        try:
            await interaction.channel.delete()

        except discord.Forbidden:
            pass


# =========================================================
# فحص صلاحية أوامر التكت
# =========================================================

async def ticket_check(interaction: discord.Interaction):

    if not is_ticket(interaction.channel):

        await interaction.response.send_message(
            "❌ هذا الأمر يعمل داخل التكتات فقط.",
            ephemeral=True
        )

        return False

    if not is_staff(interaction.user):

        embed = discord.Embed(
            title="❌ غير مسموح",
            description="هذا الأمر متاح للإدارة فقط.",
            color=discord.Color.red()
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

        return False

    return True


# =========================================================
# نداء صاحب التكت
# =========================================================

class TicketCommands(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # -----------------------------------------------------
    # /ticket_call
    # -----------------------------------------------------

    @app_commands.command(
        name="ticket_call",
        description="نداء صاحب التكت في الخاص"
    )
    async def ticket_call(
        self,
        interaction: discord.Interaction
    ):

        if not await ticket_check(interaction):
            return

        owner_id = get_ticket_owner(
            interaction.channel
        )

        if not owner_id:

            return await interaction.response.send_message(
                "❌ لم أستطع معرفة صاحب التكت.",
                ephemeral=True
            )

        member = interaction.guild.get_member(owner_id)

        if not member:

            return await interaction.response.send_message(
                "❌ العضو غير موجود في السيرفر.",
                ephemeral=True
            )

        try:

            embed = discord.Embed(
                title="🔔 نداء من الإدارة",
                description=(
                    f"لديك نداء في التكت "
                    f"**{interaction.channel.name}**.\n\n"
                    "يرجى التوجه للتكت."
                ),
                color=discord.Color.orange()
            )

            await member.send(embed=embed)

            await interaction.response.send_message(
                f"✅ تم إرسال نداء إلى {member.mention}.",
                ephemeral=True
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ لا أستطيع إرسال رسالة خاصة لهذا العضو.",
                ephemeral=True
            )

    # -----------------------------------------------------
    # /ticket_rename
    # -----------------------------------------------------

    @app_commands.command(
        name="ticket_rename",
        description="تغيير اسم التكت"
    )
    @app_commands.describe(
        name="الاسم الجديد"
    )
    async def ticket_rename(
        self,
        interaction: discord.Interaction,
        name: str
    ):

        if not await ticket_check(interaction):
            return

        name = name.strip()

        if not name:

            return await interaction.response.send_message(
                "❌ اكتب اسماً صحيحاً.",
                ephemeral=True
            )

        if not name.startswith(
            ("ticket-", "closed-")
        ):
            name = f"ticket-{name}"

        name = name[:100]

        try:

            await interaction.channel.edit(
                name=name
            )

            await interaction.response.send_message(
                f"✅ تم تغيير الاسم إلى `{name}`."
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ البوت لا يملك صلاحية تغيير اسم الروم.",
                ephemeral=True
            )

    # -----------------------------------------------------
    # /ticket_add
    # -----------------------------------------------------

    @app_commands.command(
        name="ticket_add",
        description="إضافة شخص إلى التكت"
    )
    @app_commands.describe(
        member="الشخص الذي تريد إضافته"
    )
    async def ticket_add(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):

        if not await ticket_check(interaction):
            return

        try:

            await interaction.channel.set_permissions(
                member,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            )

            await interaction.response.send_message(
                f"✅ تمت إضافة {member.mention} إلى التكت."
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ لا أملك صلاحية تعديل الروم.",
                ephemeral=True
            )

    # -----------------------------------------------------
    # /ticket_remove
    # -----------------------------------------------------

    @app_commands.command(
        name="ticket_remove",
        description="إزالة شخص من التكت"
    )
    @app_commands.describe(
        member="الشخص الذي تريد إزالته"
    )
    async def ticket_remove(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):

        if not await ticket_check(interaction):
            return

        owner_id = get_ticket_owner(
            interaction.channel
        )

        if owner_id == member.id:

            return await interaction.response.send_message(
                "❌ لا يمكنك إزالة صاحب التكت.",
                ephemeral=True
            )

        try:

            await interaction.channel.set_permissions(
                member,
                overwrite=None
            )

            await interaction.response.send_message(
                f"✅ تمت إزالة {member.mention} من التكت."
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ لا أملك صلاحية تعديل الروم.",
                ephemeral=True
            )

    # -----------------------------------------------------
    # /ticket_close
    # -----------------------------------------------------

    @app_commands.command(
        name="ticket_close",
        description="إغلاق التكت"
    )
    async def ticket_close(
        self,
        interaction: discord.Interaction
    ):

        if not await ticket_check(interaction):
            return

        owner_id = get_ticket_owner(
            interaction.channel
        )

        if owner_id:

            member = interaction.guild.get_member(
                owner_id
            )

            if member:

                try:

                    await interaction.channel.set_permissions(
                        member,
                        view_channel=True,
                        send_messages=False,
                        read_message_history=True
                    )

                except discord.Forbidden:
                    pass

        new_name = interaction.channel.name

        if not new_name.startswith("closed-"):
            new_name = f"closed-{new_name}"

        await interaction.channel.edit(
            name=new_name[:100]
        )

        embed = discord.Embed(
            title="🔒 تم إغلاق التكت",
            description=(
                f"تم إغلاق التكت بواسطة "
                f"{interaction.user.mention}."
            ),
            color=discord.Color.red()
        )

        await interaction.response.send_message(
            embed=embed,
            view=ClosedTicketView()
        )

    # -----------------------------------------------------
    # /ticket_panel
    # -----------------------------------------------------

app_commands.command(
        name="ticket_panel",
        description="إرسال لوحة التكت"
    )
    async def ticket_panel(
        self,
        interaction: discord.Interaction
    ):

        if interaction.channel_id != TICKET_PANEL_CHANNEL_ID:

            return await interaction.response.send_message(
                f"❌ استخدم الأمر في <#{TICKET_PANEL_CHANNEL_ID}>.",
                ephemeral=True
            )

        if not is_staff(interaction.user):

            return await interaction.response.send_message(
                "❌ هذا الأمر للإدارة فقط.",
                ephemeral=True
            )

        # =================================================
        # القوانين فقط
        # =================================================

        embed = discord.Embed(
            title="قـوانـيـن التذكرة 🎟️",
            description=(
                "- ممنوع سب أو شتم اي شخص\n\n"
                "- احترام الجميع\n\n"
                "- ممنوع تفتح تكت بلا سبب\n\n"
                "- ما ترد بعد يوم كامل يتسكر التكت\n\n"
                "- اجباري إحضار دليل للمشكلة أو الشكوى\n\n"
                "- احترام قوانين الدعم الفني و الإدارة\n\n"
                "- ملاحظه🔴\n\n"
                "- جهلك بالقوانين لا يعفيك من العقوبة"
            ),
            color=discord.Color.blurple()
        )

        await interaction.channel.send(
            embed=embed,
            view=TicketPanelView()
        )

        await interaction.response.send_message(
            "✅ تم إرسال لوحة التكت.",
            ephemeral=True
        )


# =========================================================
# Setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        TicketCommands(bot)
    )
