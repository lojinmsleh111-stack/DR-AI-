import asyncio
import os
import discord
from discord.ext import commands
from discord import app_commands


# =========================================================
# SETTINGS
# =========================================================

TICKET_PANEL_CHANNEL_ID = 1532414409303916655

# شكوى إدارية + تكت شراء
ADMIN_TICKET_ROLE_ID = 1532414187685413055

# الدعم الفني
STAFF_ROLE_IDS = {
    1532414218756686114,
    1532414202558283980,
}

# ضع ID روم اللوقات هنا
TICKET_LOG_CHANNEL_ID = int(os.getenv("TICKET_LOG_CHANNEL_ID", "1532414624995999876"))



# =========================================================
# HELPERS
# =========================================================

def is_staff(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    return any(role.id in STAFF_ROLE_IDS for role in member.roles)


def can_manage_ticket(member: discord.Member, ticket_type: str | None) -> bool:
    if member.guild_permissions.administrator:
        return True
    if ticket_type in ("شكوى إدارية", "شراء"):
        return ADMIN_TICKET_ROLE_ID in [role.id for role in member.roles]
    if ticket_type == "دعم فني":
        return is_staff(member)
    return False


def get_ticket_owner(channel):
    topic = getattr(channel, "topic", None)
    if not topic or not topic.startswith("ticket_owner:"):
        return None
    try:
        return int(topic.split(":", 1)[1].split("|", 1)[0])
    except (ValueError, IndexError):
        return None


def get_ticket_type(channel):
    topic = getattr(channel, "topic", None)
    if not topic or "ticket_type:" not in topic:
        return None
    try:
        return topic.split("ticket_type:", 1)[1].split("|", 1)[0]
    except (ValueError, IndexError):
        return None


def is_ticket(channel) -> bool:
    return isinstance(channel, discord.TextChannel) and channel.name.startswith(("ticket-", "closed-"))


async def send_ticket_log(guild, title, description, color=discord.Color.blurple(), fields=None):
    if not TICKET_LOG_CHANNEL_ID:
        return
    channel = guild.get_channel(TICKET_LOG_CHANNEL_ID) if TICKET_LOG_CHANNEL_ID else None
    if not isinstance(channel, discord.TextChannel):
        channel = discord.utils.get(guild.text_channels, name=TICKET_LOG_CHANNEL_NAME)
    if not isinstance(channel, discord.TextChannel):
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=discord.utils.utcnow()
    )
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    try:
        await channel.send(embed=embed)
    except discord.HTTPException:
        pass


async def check_ticket_staff(interaction: discord.Interaction) -> bool:
    if not is_ticket(interaction.channel):
        await interaction.response.send_message("❌ هذا الأمر يعمل داخل التكتات فقط.", ephemeral=True)
        return False

    ticket_type = get_ticket_type(interaction.channel)
    if not can_manage_ticket(interaction.user, ticket_type):
        await interaction.response.send_message("❌ ليس لديك صلاحية إدارة هذا النوع من التكتات.", ephemeral=True)
        return False
    return True


# =========================================================
# RATING
# =========================================================

class TicketRatingView(discord.ui.View):
    def __init__(self, bot, guild_id: int, ticket_id: int, member_id: int):
        super().__init__(timeout=86400)
        self.bot = bot
        self.guild_id = guild_id
        self.ticket_id = ticket_id
        self.member_id = member_id
        self.rated = False

    async def rate(self, interaction, rating):
        if interaction.user.id != self.member_id:
            await interaction.response.send_message("❌ هذا التقييم ليس مخصصًا لك.", ephemeral=True)
            return
        if self.rated:
            await interaction.response.send_message("❌ تم تسجيل تقييمك مسبقًا.", ephemeral=True)
            return
        self.rated = True
        await interaction.response.send_message(f"⭐ شكراً لك! تم تسجيل تقييمك: **{rating}/5**.", ephemeral=True)
        guild = self.bot.get_guild(self.guild_id)
        if guild:
            await send_ticket_log(
                guild, "⭐ تقييم تكت",
                f"تم تقييم التكت بواسطة {interaction.user.mention}.",
                discord.Color.gold(),
                [("التقييم", f"**{rating}/5** ⭐", True), ("العضو", interaction.user.mention, True),
                 ("ID العضو", str(interaction.user.id), True), ("Ticket ID", str(self.ticket_id), True)]
            )
        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except discord.HTTPException:
            pass

    @discord.ui.button(label="1", emoji="⭐", style=discord.ButtonStyle.secondary, custom_id="ticket_rating_1")
    async def one(self, interaction, button):
        await self.rate(interaction, 1)

    @discord.ui.button(label="2", emoji="⭐", style=discord.ButtonStyle.secondary, custom_id="ticket_rating_2")
    async def two(self, interaction, button):
        await self.rate(interaction, 2)

    @discord.ui.button(label="3", emoji="⭐", style=discord.ButtonStyle.secondary, custom_id="ticket_rating_3")
    async def three(self, interaction, button):
        await self.rate(interaction, 3)

    @discord.ui.button(label="4", emoji="⭐", style=discord.ButtonStyle.secondary, custom_id="ticket_rating_4")
    async def four(self, interaction, button):
        await self.rate(interaction, 4)

    @discord.ui.button(label="5", emoji="⭐", style=discord.ButtonStyle.success, custom_id="ticket_rating_5")
    async def five(self, interaction, button):
        await self.rate(interaction, 5)


async def send_rating_dm(bot, member, channel):
    embed = discord.Embed(
        title="⭐ تقييم التكت",
        description="تم إغلاق التكت الخاص بك.\n\nنقدر تقييمك لخدمة الدعم، اختر التقييم المناسب من 1 إلى 5 ⭐.",
        color=discord.Color.gold()
    )
    try:
        view = TicketRatingView(bot, member.guild.id, channel.id, member.id)
        await member.send(embed=embed, view=view)
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False


# =========================================================
# TICKET PANEL
# =========================================================

class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketTypeSelect())


class TicketTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="تذكرة إدارية", description="فتح تذكرة إدارية", emoji="🛠️", value="شكوى إدارية"),
            discord.SelectOption(label="الدعم الفني", description="فتح تذكرة للدعم الفني", emoji="🖥️", value="دعم فني"),
            discord.SelectOption(label="تذكرة الشراء", description="فتح تذكرة لشراء رتبة او لطلب اعلان", emoji="💸", value="شراء"),
        ]
        super().__init__(placeholder="🎟️ اختر نوع التذكرة...", min_values=1, max_values=1, options=options, custom_id="ticket_type_select")

    async def callback(self, interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("❌ حدث خطأ.", ephemeral=True)
            return

        panel_channel = guild.get_channel(TICKET_PANEL_CHANNEL_ID)
        if not isinstance(panel_channel, discord.TextChannel):
            await interaction.response.send_message("❌ لم يتم العثور على روم لوحة التكت.", ephemeral=True)
            return

        for channel in guild.text_channels:
            if is_ticket(channel) and get_ticket_owner(channel) == interaction.user.id:
                await interaction.response.send_message(f"❌ عندك تكت مفتوح بالفعل: {channel.mention}", ephemeral=True)
                return

        category = panel_channel.category
        if category is None:
            await interaction.response.send_message("❌ روم لوحة التكت يجب أن يكون داخل Category.", ephemeral=True)
            return

        ticket_type = self.values[0]
        data = {
            "شكوى إدارية": (f"ticket-admin-{interaction.user.name}", "🛠️ التذكرة الإدارية"),
            "دعم فني": (f"ticket-support-{interaction.user.name}", "🖥️ تذكرة الدعم الفني"),
            "شراء": (f"ticket-buy-{interaction.user.name}", "💸 تذكرة الشراء"),
        }
        channel_name, title = data[ticket_type]
        channel_name = channel_name.lower().replace(" ", "-")[:100]

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
                attach_files=True, embed_links=True
            )
        }

        if guild.me:
            overwrites[guild.me] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
                manage_channels=True, manage_messages=True, manage_permissions=True,
                attach_files=True, embed_links=True
            )

        # الشكوى الإدارية والشراء: فقط الرتبة المحددة
        if ticket_type in ("شكوى إدارية", "شراء"):
            role = guild.get_role(ADMIN_TICKET_ROLE_ID)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True,
                    manage_messages=True, attach_files=True, embed_links=True
                )

        # الدعم الفني: الرتبتان المحددتان
        if ticket_type == "دعم فني":
            for role_id in STAFF_ROLE_IDS:
                role = guild.get_role(role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        view_channel=True, send_messages=True, read_message_history=True,
                        manage_messages=True, attach_files=True, embed_links=True
                    )

        try:
            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"ticket_owner:{interaction.user.id}|ticket_type:{ticket_type}"
            )
        except discord.Forbidden:
            await interaction.response.send_message("❌ البوت لا يملك صلاحية إنشاء التكت أو تعديل الصلاحيات.", ephemeral=True)
            return
        except discord.HTTPException:
            await interaction.response.send_message("❌ حدث خطأ أثناء إنشاء التكت.", ephemeral=True)
            return

        embed = discord.Embed(
            title=title,
            description=f"مرحباً {interaction.user.mention} 👋\n\nتم فتح التكت بنجاح.\nاكتب طلبك وانتظر الإدارة.",
            color=discord.Color.blurple()
        )
        await channel.send(content=interaction.user.mention, embed=embed, view=TicketControlView())

        await send_ticket_log(
            guild, "🎟️ فتح تكت جديد", f"تم فتح تكت جديد بواسطة {interaction.user.mention}.", discord.Color.green(),
            [("نوع التكت", ticket_type, True), ("العضو", interaction.user.mention, True),
             ("ID العضو", str(interaction.user.id), True), ("التكت", channel.mention, True),
             ("الرابط", f"[اضغط هنا]({channel.jump_url})", True)]
        )

        await interaction.response.send_message(f"✅ تم فتح التكت: {channel.mention}", ephemeral=True)


# =========================================================
# TICKET BUTTONS
# =========================================================

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="استلام", emoji="🙋", style=discord.ButtonStyle.success, custom_id="ticket_claim")
    async def claim(self, interaction, button):
        if not await check_ticket_staff(interaction):
            return
        await interaction.response.send_message(f"🙋 تم استلام التكت بواسطة {interaction.user.mention}.")
        await send_ticket_log(interaction.guild, "🙋 استلام تكت", f"تم استلام التكت بواسطة {interaction.user.mention}.", discord.Color.green(),
                               [("التكت", interaction.channel.mention, True), ("المستلم", interaction.user.mention, True)])

    @discord.ui.button(label="إغلاق", emoji="🔒", style=discord.ButtonStyle.secondary, custom_id="ticket_close")
    async def close(self, interaction, button):
        if not await check_ticket_staff(interaction):
            return

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return

        owner_id = get_ticket_owner(channel)
        ticket_type = get_ticket_type(channel)
        member = interaction.guild.get_member(owner_id) if owner_id else None

        if member:
            try:
                await channel.set_permissions(member, view_channel=True, send_messages=False, read_message_history=True)
            except discord.Forbidden:
                pass

        new_name = channel.name if channel.name.startswith("closed-") else f"closed-{channel.name}"
        try:
            await channel.edit(name=new_name[:100])
        except discord.Forbidden:
            await interaction.response.send_message("❌ البوت لا يملك صلاحية تغيير اسم الروم.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔒 تم إغلاق التكت",
            description=f"تم إغلاق التكت بواسطة {interaction.user.mention}.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, view=ClosedTicketView())

        rating_sent = await send_rating_dm(self.bot, member, channel) if member else False
        await send_ticket_log(
            interaction.guild, "🔒 إغلاق تكت", f"تم إغلاق التكت بواسطة {interaction.user.mention}.", discord.Color.red(),
            [("نوع التكت", ticket_type or "غير معروف", True),
             ("صاحب التكت", member.mention if member else "غير معروف", True),
             ("المغلق", interaction.user.mention, True),
             ("التقييم بالخاص", "تم الإرسال" if rating_sent else "تعذر الإرسال", True),
             ("الرابط", f"[اضغط هنا]({channel.jump_url})", True)]
        )

    @discord.ui.button(label="حذف", emoji="🗑️", style=discord.ButtonStyle.danger, custom_id="ticket_delete")
    async def delete(self, interaction, button):
        if not await check_ticket_staff(interaction):
            return
        channel = interaction.channel
        await send_ticket_log(
            interaction.guild, "🗑️ حذف تكت", f"سيتم حذف التكت بواسطة {interaction.user.mention}.", discord.Color.dark_red(),
            [("نوع التكت", get_ticket_type(channel) or "غير معروف", True),
             ("صاحب التكت", f"<@{get_ticket_owner(channel)}>" if get_ticket_owner(channel) else "غير معروف", True),
             ("الحاذف", interaction.user.mention, True), ("الروم", channel.name, True)]
        )
        await interaction.response.send_message("🗑️ سيتم حذف التكت خلال 5 ثوانٍ.")
        await asyncio.sleep(5)
        try:
            await channel.delete()
        except discord.Forbidden:
            pass


class ClosedTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="حذف التكت", emoji="🗑️", style=discord.ButtonStyle.danger, custom_id="closed_ticket_delete")
    async def delete(self, interaction, button):
        if not await check_ticket_staff(interaction):
            return
        channel = interaction.channel
        await send_ticket_log(
            interaction.guild, "🗑️ حذف تكت مغلق", f"تم حذف التكت بواسطة {interaction.user.mention}.", discord.Color.dark_red(),
            [("نوع التكت", get_ticket_type(channel) or "غير معروف", True),
             ("صاحب التكت", f"<@{get_ticket_owner(channel)}>" if get_ticket_owner(channel) else "غير معروف", True),
             ("الحاذف", interaction.user.mention, True), ("الروم", channel.name, True)]
        )
        await interaction.response.send_message("🗑️ سيتم حذف التكت خلال 5 ثوانٍ.")
        await asyncio.sleep(5)
        try:
            await channel.delete()
        except discord.Forbidden:
            pass


# =========================================================
# COG
# =========================================================

class SupportTickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ticket_panel", description="إرسال لوحة التكت")
    async def ticket_panel(self, interaction):
        if interaction.channel_id != TICKET_PANEL_CHANNEL_ID:
            await interaction.response.send_message(f"❌ استخدم الأمر في <#{TICKET_PANEL_CHANNEL_ID}>.", ephemeral=True)
            return
        if not (
            interaction.user.guild_permissions.administrator
            or is_staff(interaction.user)
            or any(role.id == ADMIN_TICKET_ROLE_ID for role in interaction.user.roles)
        ):
            await interaction.response.send_message("❌ هذا الأمر للإدارة فقط.", ephemeral=True)
            return

        embed = discord.Embed(
            title="قـوانـيـن التذكرة 🎟️",
            description="- ممنوع سب أو شتم اي شخص\n\n- احترام الجميع\n\n- ممنوع تفتح تكت بلا سبب\n\n- ما ترد بعد يوم كامل يتسكر التكت\n\n- اجباري إحضار دليل للمشكلة أو الشكوى\n\n- احترام قوانين الدعم الفني و الإدارة\n\n- ملاحظه🔴\n\n- جهلك بالقوانين لا يعفيك من العقوبة",
            color=discord.Color.blurple()
        )
        await interaction.channel.send(embed=embed, view=TicketPanelView())
        await interaction.response.send_message("✅ تم إرسال لوحة التكت.", ephemeral=True)

    @app_commands.command(name="ticket_call", description="نداء صاحب التكت في الخاص")
    async def ticket_call(self, interaction):
        if not await check_ticket_staff(interaction):
            return
        owner_id = get_ticket_owner(interaction.channel)
        if not owner_id:
            await interaction.response.send_message("❌ لم أستطع معرفة صاحب التكت.", ephemeral=True)
            return
        member = interaction.guild.get_member(owner_id)
        if not member:
            await interaction.response.send_message("❌ العضو غير موجود في السيرفر.", ephemeral=True)
            return
        try:
            embed = discord.Embed(title="🔔 نداء من الإدارة", description=f"لديك نداء في التكت **{interaction.channel.name}**.\n\nيرجى التوجه للتكت.", color=discord.Color.orange())
            await member.send(embed=embed)
            await interaction.response.send_message(f"✅ تم إرسال نداء إلى {member.mention}.", ephemeral=True)
            await send_ticket_log(interaction.guild, "🔔 نداء عضو", f"تم إرسال نداء لصاحب التكت بواسطة {interaction.user.mention}.", discord.Color.orange(),
                                   [("العضو", member.mention, True), ("المنادي", interaction.user.mention, True), ("التكت", interaction.channel.mention, True)])
        except discord.Forbidden:
            await interaction.response.send_message("❌ لا أستطيع إرسال رسالة خاصة لهذا العضو.", ephemeral=True)

    @app_commands.command(name="ticket_rename", description="تغيير اسم التكت")
    @app_commands.describe(name="الاسم الجديد")
    async def ticket_rename(self, interaction, name: str):
        if not await check_ticket_staff(interaction):
            return
        name = name.strip().lower().replace(" ", "-")
        if not name:
            await interaction.response.send_message("❌ اكتب اسماً صحيحاً.", ephemeral=True)
            return
        if not name.startswith(("ticket-", "closed-")):
            name = f"ticket-{name}"
        old_name = interaction.channel.name
        try:
            await interaction.channel.edit(name=name[:100])
            await interaction.response.send_message(f"✅ تم تغيير الاسم إلى `{name[:100]}`.")
            await send_ticket_log(interaction.guild, "✏️ تغيير اسم تكت", f"تم تغيير اسم التكت بواسطة {interaction.user.mention}.", discord.Color.blurple(),
                                   [("السابق", old_name, True), ("الجديد", name[:100], True), ("المسؤول", interaction.user.mention, True)])
        except discord.Forbidden:
            await interaction.response.send_message("❌ البوت لا يملك صلاحية تغيير اسم الروم.", ephemeral=True)

    @app_commands.command(name="ticket_add", description="إضافة شخص إلى التكت")
    @app_commands.describe(member="الشخص الذي تريد إضافته")
    async def ticket_add(self, interaction, member: discord.Member):
        if not await check_ticket_staff(interaction):
            return
        try:
            await interaction.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True)
            await interaction.response.send_message(f"✅ تمت إضافة {member.mention} إلى التكت.")
            await send_ticket_log(interaction.guild, "➕ إضافة عضو", f"تمت إضافة {member.mention} إلى التكت.", discord.Color.green(),
                                   [("المسؤول", interaction.user.mention, True), ("العضو", member.mention, True), ("التكت", interaction.channel.mention, True)])
        except discord.Forbidden:
            await interaction.response.send_message("❌ لا أملك صلاحية تعديل الروم.", ephemeral=True)

    @app_commands.command(name="ticket_remove", description="إزالة شخص من التكت")
    @app_commands.describe(member="الشخص الذي تريد إزالته")
    async def ticket_remove(self, interaction, member: discord.Member):
        if not await check_ticket_staff(interaction):
            return
        if get_ticket_owner(interaction.channel) == member.id:
            await interaction.response.send_message("❌ لا يمكنك إزالة صاحب التكت.", ephemeral=True)
            return
        try:
            await interaction.channel.set_permissions(member, overwrite=None)
            await interaction.response.send_message(f"✅ تمت إزالة {member.mention} من التكت.")
            await send_ticket_log(interaction.guild, "➖ إزالة عضو", f"تمت إزالة {member.mention} من التكت.", discord.Color.orange(),
                                   [("المسؤول", interaction.user.mention, True), ("العضو", member.mention, True), ("التكت", interaction.channel.mention, True)])
        except discord.Forbidden:
            await interaction.response.send_message("❌ لا أملك صلاحية تعديل الروم.", ephemeral=True)

    @app_commands.command(name="ticket_close", description="إغلاق التكت")
    async def ticket_close(self, interaction):
        if not await check_ticket_staff(interaction):
            return
        channel = interaction.channel
        owner_id = get_ticket_owner(channel)
        ticket_type = get_ticket_type(channel)
        member = interaction.guild.get_member(owner_id) if owner_id else None
        if member:
            try:
                await channel.set_permissions(member, view_channel=True, send_messages=False, read_message_history=True)
            except discord.Forbidden:
                pass
        new_name = channel.name if channel.name.startswith("closed-") else f"closed-{channel.name}"
        try:
            await channel.edit(name=new_name[:100])
        except discord.Forbidden:
            await interaction.response.send_message("❌ البوت لا يملك صلاحية تغيير اسم الروم.", ephemeral=True)
            return
        embed = discord.Embed(title="🔒 تم إغلاق التكت", description=f"تم إغلاق التكت بواسطة {interaction.user.mention}.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, view=ClosedTicketView())
        rating_sent = await send_rating_dm(member, channel) if member else False
        await send_ticket_log(interaction.guild, "🔒 إغلاق تكت", f"تم إغلاق التكت بواسطة {interaction.user.mention}.", discord.Color.red(),
                               [("نوع التكت", ticket_type or "غير معروف", True), ("صاحب التكت", member.mention if member else "غير معروف", True),
                                ("المغلق", interaction.user.mention, True), ("التقييم بالخاص", "تم الإرسال" if rating_sent else "تعذر الإرسال", True),
                                ("الرابط", f"[اضغط هنا]({channel.jump_url})", True)])


# =========================================================
# SETUP
# =========================================================

async def setup(bot):
    await bot.add_cog(SupportTickets(bot))
    bot.add_view(TicketPanelView())
    bot.add_view(TicketControlView())
    bot.add_view(ClosedTicketView())
