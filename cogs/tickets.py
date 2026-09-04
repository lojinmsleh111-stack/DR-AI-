import discord
from discord import app_commands
from discord.ext import commands, tasks

import json
import os
import logging
from datetime import datetime, timedelta


logger = logging.getLogger("bot")


# =========================================================
# IDs - DR-AI
# =========================================================

USERS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "users.json"
)

TICKET_ALLOWED_CHANNEL_ID = 1532414607577055465
PAYMENT_OFFICER_ROLE_ID = 1532414219843276820
STAFF_ROLE_ID = 1532414219843276820
OVERDUE_ROLE_ID = 1533068412547497984
GUILD_ID = 1532390688187220159


# =========================================================
# Emojis
# =========================================================

PAID_EMOJI_ID = 1537811911054196877
UNPAID_EMOJI_ID = 1537811948027117599


# =========================================================
# Users JSON
# =========================================================

def load_users() -> dict:
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {}


def save_users(data: dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# Get Emoji
# =========================================================

async def get_custom_emoji(
    guild: discord.Guild,
    emoji_id: int
):
    emoji = guild.get_emoji(emoji_id)

    if emoji:
        return emoji

    try:
        return await guild.fetch_emoji(emoji_id)
    except (
        discord.NotFound,
        discord.Forbidden,
        discord.HTTPException
    ):
        return None


# =========================================================
# Update Violation Status
# =========================================================

async def update_violation_status(
    interaction: discord.Interaction,
    message_id: int,
    emoji_id: int
):

    try:
        guild = interaction.guild

        if guild is None:
            return False

        channel = guild.get_channel(
            TICKET_ALLOWED_CHANNEL_ID
        )

        if channel is None:
            try:
                channel = await interaction.client.fetch_channel(
                    TICKET_ALLOWED_CHANNEL_ID
                )
            except Exception:
                return False

        if not isinstance(channel, discord.TextChannel):
            return False

        try:
            message = await channel.fetch_message(
                message_id
            )
        except Exception:
            return False

        bot_user = guild.me

        # إزالة إيموجي الحالة القديم
        for reaction in list(message.reactions):

            if not isinstance(
                reaction.emoji,
                discord.Emoji
            ):
                continue

            if reaction.emoji.id not in (
                PAID_EMOJI_ID,
                UNPAID_EMOJI_ID
            ):
                continue

            try:
                await message.remove_reaction(
                    reaction.emoji,
                    bot_user
                )
            except Exception:
                pass

        # جلب الإيموجي الجديد
        emoji = await get_custom_emoji(
            guild,
            emoji_id
        )

        if emoji is None:
            return False

        await message.add_reaction(
            emoji
        )

        return True

    except Exception as e:
        logger.error(
            f"Error updating violation status: {e}"
        )
        return False


# =========================================================
# Violation Status Button
# =========================================================

class ViolationStatusButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"violation_status:(?P<status>paid|unpaid):(?P<message_id>[0-9]+)"
):

    def __init__(
        self,
        status: str,
        message_id: int
    ):

        self.status = status
        self.message_id = message_id

        if status == "paid":
            label = "تم السداد"
            style = discord.ButtonStyle.success
        else:
            label = "لم يتم السداد"
            style = discord.ButtonStyle.danger

        super().__init__(
            discord.ui.Button(
                label=label,
                style=style,
                custom_id=(
                    f"violation_status:"
                    f"{status}:"
                    f"{message_id}"
                )
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item,
        match,
        /
    ):
        return cls(
            match["status"],
            int(match["message_id"])
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        if interaction.guild is None:
            return await interaction.followup.send(
                "❌ هذا الزر يعمل داخل السيرفر فقط.",
                ephemeral=True
            )

        # =====================================================
        # صلاحية العسكري
        # =====================================================

        officer_role = interaction.guild.get_role(
            PAYMENT_OFFICER_ROLE_ID
        )

        if (
            officer_role not in interaction.user.roles
            and not interaction.user.guild_permissions.administrator
        ):
            return await interaction.followup.send(
                "❌ هذا الزر مخصص للضباط المصرح لهم فقط!",
                ephemeral=True
            )

        # =====================================================
        # البحث عن المخالفة
        # =====================================================

        users = load_users()

        found_ticket = None

        for user_id, data in users.items():

            tickets = data.get(
                "tickets",
                []
            )

            for index, ticket in enumerate(tickets):

                if str(
                    ticket.get("message_id")
                ) == str(
                    self.message_id
                ):

                    found_ticket = (
                        user_id,
                        index,
                        ticket
                    )

                    break

            if found_ticket:
                break

        if found_ticket is None:
            return await interaction.followup.send(
                "❌ لم يتم العثور على سجل المخالفة!",
                ephemeral=True
            )

        user_id, ticket_index, ticket = found_ticket

        # =====================================================
        # تحديث حالة السداد
        # =====================================================

        if self.status == "paid":
            ticket["paid"] = True
        else:
            ticket["paid"] = False

        save_users(users)

        # =====================================================
        # تحديث الإيموجي
        # =====================================================

        emoji_id = (
            PAID_EMOJI_ID
            if self.status == "paid"
            else UNPAID_EMOJI_ID
        )

        updated = await update_violation_status(
            interaction,
            self.message_id,
            emoji_id
        )

        if not updated:
            return await interaction.followup.send(
                "⚠️ تم تحديث حالة المخالفة، لكن تعذر تحديث الإيموجي في الرسالة الأصلية.",
                ephemeral=True
            )

        # =====================================================
        # تم السداد
        # =====================================================

        if self.status == "paid":

            await interaction.followup.send(
                "✅ تم تسجيل المخالفة كـ **تم السداد** وتحديث الإيموجي.",
                ephemeral=True
            )

            member = interaction.guild.get_member(
                int(user_id)
            )

            if member:

                all_paid = all(
                    t.get("paid", False)
                    for t in users[user_id].get(
                        "tickets",
                        []
                    )
                )

                if all_paid:

                    overdue_role = interaction.guild.get_role(
                        OVERDUE_ROLE_ID
                    )

                    if (
                        overdue_role
                        and overdue_role in member.roles
                    ):

                        try:

                            await member.remove_roles(
                                overdue_role
                            )

                            await interaction.channel.send(
                                f"🟢 **تحديث:** تم رفع إيقاف الخدمات عن المواطن {member.mention}"
                            )

                        except Exception:
                            pass

        # =====================================================
        # لم يتم السداد
        # =====================================================

        else:

            await interaction.followup.send(
                "🔴 تم تسجيل المخالفة كـ **لم يتم السداد** وتحديث الإيموجي.",
                ephemeral=True
            )


# =========================================================
# Violation View
# =========================================================

class ViolationView(discord.ui.View):

    def __init__(
        self,
        message_id: int
    ):

        super().__init__(
            timeout=None
        )

        self.add_item(
            ViolationStatusButton(
                "paid",
                message_id
            )
        )

        self.add_item(
            ViolationStatusButton(
                "unpaid",
                message_id
            )
        )


# =========================================================
# Tickets Cog
# =========================================================

class Tickets(commands.Cog):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

        # تشغيل فحص المخالفات المتأخرة
        self.check_overdue_tickets.start()

    def cog_unload(self):

        self.check_overdue_tickets.cancel()

    # =====================================================
    # /مخالفة
    # =====================================================

    @app_commands.command(
        name="مخالفة",
        description="إصدار مخالفة"
    )
    @app_commands.describe(
        target="المخالف",
        reason="سبب المخالفة",
        amount="مبلغ المخالفة",
        plate="رقم اللوحة",
        proof="الدليل - صورة"
    )
    async def make_ticket(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        reason: str,
        amount: int,
        plate: str,
        proof: discord.Attachment
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        # =====================================================
        # السيرفر
        # =====================================================

        if interaction.guild is None:
            return await interaction.followup.send(
                "❌ هذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True
            )

        # =====================================================
        # الروم المسموح
        # =====================================================

        if interaction.channel_id != TICKET_ALLOWED_CHANNEL_ID:
            return await interaction.followup.send(
                "❌ لا يمكنك استخدام أمر المخالفة في هذا الروم.",
                ephemeral=True
            )

        # =====================================================
        # صلاحية العسكري
        # =====================================================

        staff_role = interaction.guild.get_role(
            STAFF_ROLE_ID
        )

        if (
            staff_role not in interaction.user.roles
            and not interaction.user.guild_permissions.administrator
        ):
            return await interaction.followup.send(
                "❌ ليس لديك صلاحية إصدار المخالفات.",
                ephemeral=True
            )

        # =====================================================
        # المبلغ
        # =====================================================

        if amount <= 0:
            return await interaction.followup.send(
                "❌ يجب أن يكون مبلغ المخالفة أكبر من 0.",
                ephemeral=True
            )

        # =====================================================
        # الدليل
        # =====================================================

        if (
            proof.content_type is None
            or not proof.content_type.startswith("image/")
        ):
            return await interaction.followup.send(
                "❌ الدليل يجب أن يكون صورة.",
                ephemeral=True
            )

        # =====================================================
        # RP ID
        # =====================================================

        users = load_users()

        user_key = str(
            target.id
        )

        existing_data = users.get(
            user_key,
            {}
        )

        rp_id = existing_data.get(
            "rp_id",
            "غير مسجل"
        )

        # =====================================================
        # إنشاء بيانات المستخدم
        # =====================================================

        if user_key not in users:

            users[user_key] = {
                "discord_tag": str(target),
                "real_name": target.display_name,
                "rp_id": rp_id,
                "tickets": [],
                "permits": []
            }

        if "tickets" not in users[user_key]:
            users[user_key]["tickets"] = []

        # =====================================================
        # بيانات المخالفة
        # =====================================================

        ticket_data = {
            "amount": amount,
            "reason": reason,
            "plate": plate,
            "issuer": interaction.user.display_name,
            "issuer_id": interaction.user.id,
            "issued_at": datetime.now().isoformat(),
            "paid": False,
            "proof_url": proof.url,
            "message_id": None
        }

        users[user_key]["tickets"].append(
            ticket_data
        )

        ticket_index = len(
            users[user_key]["tickets"]
        ) - 1

        save_users(users)

        # =====================================================
        # نموذج المخالفة - نفس النموذج المطلوب
        # =====================================================

        violation_text = (
            "**__تم اصدار مخالفه\n\n"
            f"العسكري : {interaction.user.mention}\n\n"
            f"المخالف : {target.mention}\n\n"
            f"سبب المخالفة : {reason}\n\n"
            f"مبلغ المخالفة : {amount}\n\n"
            f"اللوحة : {plate}\n\n"
            f"الدليل : {proof.url}\n\n"
            "الدليل الإضافي : لا يوجد\n\n\n"
            "..\n\n"
            "__**"
        )

        # =====================================================
        # إرسال الرسالة
        # =====================================================

        try:

            traffic_channel = interaction.guild.get_channel(
                TICKET_ALLOWED_CHANNEL_ID
            )

            if traffic_channel is None:
                traffic_channel = await self.bot.fetch_channel(
                    TICKET_ALLOWED_CHANNEL_ID
                )

            if not isinstance(
                traffic_channel,
                discord.TextChannel
            ):
                raise RuntimeError(
                    "Traffic channel is not a TextChannel"
                )

            message = await traffic_channel.send(
                content=violation_text,
                allowed_mentions=discord.AllowedMentions(
                    users=True
                )
            )

        except Exception as e:

            logger.error(
                f"VIOLATION SEND ERROR: {e}"
            )

            # حذف السجل الذي تم إنشاؤه إذا فشل الإرسال
            try:
                users[user_key]["tickets"].pop(
                    ticket_index
                )
                save_users(users)
            except Exception:
                pass

            return await interaction.followup.send(
                "❌ حدث خطأ أثناء إرسال المخالفة.",
                ephemeral=True
            )

        # =====================================================
        # حفظ Message ID
        # =====================================================

        users = load_users()

        try:
            users[user_key]["tickets"][
                ticket_index
            ]["message_id"] = message.id

            save_users(users)

        except Exception as e:

            logger.error(
                f"JSON MESSAGE ID ERROR: {e}"
            )

        # =====================================================
        # إضافة إيموجي لم يتم السداد
        # =====================================================

        unpaid_emoji = await get_custom_emoji(
            interaction.guild,
            UNPAID_EMOJI_ID
        )

        if unpaid_emoji:

            try:
                await message.add_reaction(
                    unpaid_emoji
                )
            except Exception as e:
                logger.error(
                    f"UNPAID REACTION ERROR: {e}"
                )

        # =====================================================
        # إنشاء Thread
        # =====================================================

        try:

            thread = await message.create_thread(
                name=f"مخالفة - {target.display_name}"
            )

            await thread.send(
                content="حالة السداد:",
                view=ViolationView(
                    message.id
                )
            )

        except Exception as e:

            logger.error(
                f"THREAD ERROR: {e}"
            )

        # =====================================================
        # إرسال الخاص للمخالف
        # =====================================================

        try:

            await target.send(
                content=violation_text,
                allowed_mentions=discord.AllowedMentions(
                    users=False
                )
            )

            dm_status = "وتم إرسالها للخاص."

        except (
            discord.Forbidden,
            discord.HTTPException
        ):

            dm_status = (
                "لكن تعذر إرسالها للخاص "
                "(قد تكون الرسائل الخاصة مقفلة)."
            )

        # =====================================================
        # التأكيد للعسكري
        # =====================================================

        await interaction.followup.send(
            f"✅ تم إصدار المخالفة بنجاح.\n{dm_status}",
            ephemeral=True
        )

    # =====================================================
    # فحص المخالفات المتأخرة
    # =====================================================

  @tasks.loop(hours=1)
    async def check_overdue_tickets(self):

        try:

            users = load_users()

            now = datetime.now()

            changed = False

            for user_id, data in users.items():

                tickets = data.get(
                    "tickets",
                    []
                )

                has_overdue = False

                for ticket in tickets:

                    if ticket.get("paid", False):
                        continue

                    issued_at = ticket.get(
                        "issued_at"
                    )

                    if not issued_at:
                        continue

                    try:
                        issued_date = datetime.fromisoformat(
                            issued_at
                        )
                    except Exception:
                        continue

                    if now - issued_date >= timedelta(
                        days=7
                    ):
                        has_overdue = True
                        break

                if not has_overdue:
                    continue

                guild = self.bot.get_guild(
                    GUILD_ID
                )

                if guild is None:
                    continue

                member = guild.get_member(
                    int(user_id)
                )

                if member is None:
                    continue

                overdue_role = guild.get_role(
                    OVERDUE_ROLE_ID
                )

                if (
                    overdue_role
                    and overdue_role not in member.roles
                ):

                    try:

                        await member.add_roles(
                            overdue_role,
                            reason="مخالفة غير مسددة لمدة 7 أيام"
                        )

                    except Exception as e:

                        logger.error(
                            f"OVERDUE ROLE ERROR: {e}"
                        )

            if changed:
                save_users(users)

        except Exception as e:

            logger.error(
                f"OVERDUE CHECK ERROR: {e}"
            )

    @check_overdue_tickets.before_loop
    async def before_overdue_check(self):

        await self.bot.wait_until_ready()


# =========================================================
# Setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        Tickets(bot)
    )

    # مهم حتى تشتغل الأزرار القديمة بعد إعادة تشغيل البوت
    bot.add_dynamic_items(
        ViolationStatusButton
    )
