import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import os
import logging
from datetime import datetime, timedelta

log = logging.getLogger("bot")

TICKET_ALLOWED_CHANNEL_ID = 1532414607577055465
PAYMENT_OFFICER_ROLE_ID = 1532414219843276820
STAFF_ROLE_ID = 1532414219843276820
OVERDUE_ROLE_ID = 1533068412547497984
GUILD_ID = 1532390688187220159

PAID_EMOJI_ID = 1537811911054196877
UNPAID_EMOJI_ID = 1537811948027117599

USERS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "users.json"
)


def load_users():
    try:
        if not os.path.exists(USERS_FILE):
            return {}

        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        log.exception("Failed to load users.json")
        return {}


def save_users(data):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=4
            )

    except Exception:
        log.exception("Failed to save users.json")


def get_custom_emoji(guild: discord.Guild, emoji_id: int):
    emoji = guild.get_emoji(emoji_id)

    if emoji:
        return str(emoji)

    return ""


async def update_violation_status(
    message: discord.Message,
    status: str
):
    guild = message.guild

    if guild is None:
        return

    paid_emoji = get_custom_emoji(
        guild,
        PAID_EMOJI_ID
    )

    unpaid_emoji = get_custom_emoji(
        guild,
        UNPAID_EMOJI_ID
    )

    try:

        if status == "paid":

            if unpaid_emoji:
                await message.remove_reaction(
                    unpaid_emoji,
                    guild.me
                )

            if paid_emoji:
                await message.add_reaction(
                    paid_emoji
                )

        else:

            if paid_emoji:
                await message.remove_reaction(
                    paid_emoji,
                    guild.me
                )

            if unpaid_emoji:
                await message.add_reaction(
                    unpaid_emoji
                )

    except Exception:
        log.exception(
            "Failed to update violation status"
        )


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

        button = discord.ui.Button(
            label=label,
            style=style,
            custom_id=(
                f"violation_status:"
                f"{status}:"
                f"{message_id}"
            )
        )

        super().__init__(button)

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item,
        match
    ):

        status = match["status"]
        message_id = int(
            match["message_id"]
        )

        return cls(
            status,
            message_id
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if interaction.guild is None:

            await interaction.response.send_message(
                "هذا الأمر داخل السيرفر فقط.",
                ephemeral=True
            )

            return

        member = interaction.user

        if not isinstance(
            member,
            discord.Member
        ):

            await interaction.response.send_message(
                "تعذر التحقق من رتبتك.",
                ephemeral=True
            )

            return

        allowed_roles = {
            PAYMENT_OFFICER_ROLE_ID,
            STAFF_ROLE_ID
        }

        if not any(
            role.id in allowed_roles
            for role in member.roles
        ):

            await interaction.response.send_message(
                "❌ ليس لديك صلاحية لتغيير حالة المخالفة.",
                ephemeral=True
            )

            return

        try:

            message = await interaction.channel.fetch_message(
                self.message_id
            )

        except Exception:

            await interaction.response.send_message(
                "❌ لم أستطع العثور على رسالة المخالفة.",
                ephemeral=True
            )

            return

        await update_violation_status(
            message,
            self.status
        )

        users = load_users()

        for user_data in users.values():

            for violation in user_data.get(
                "violations",
                []
            ):

                if violation.get(
                    "message_id"
                ) == self.message_id:

                    violation["status"] = self.status

        save_users(users)

        await interaction.response.send_message(
            "✅ تم تحديث حالة المخالفة.",
            ephemeral=True
        )


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


class Tickets(commands.Cog):

    def __init__(
        self,
        bot: commands.Bot
    ):

        self.bot = bot

        self.check_overdue_tickets.start()

    def cog_unload(self):

        self.check_overdue_tickets.cancel()

    @app_commands.command(
        name="مخالفة",
        description="إصدار مخالفة عسكرية"
    )
    @app_commands.describe(
        target="الشخص المخالف",
        reason="سبب المخالفة",
        amount="مبلغ المخالفة",
        plate="رقم اللوحة",
        proof="الدليل"
    )
    async def violation(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        reason: str,
        amount: str,
        plate: str,
        proof: discord.Attachment
    ):

        if interaction.guild is None:

            await interaction.response.send_message(
                "هذا الأمر داخل السيرفر فقط.",
                ephemeral=True
            )

            return

        if interaction.channel_id != TICKET_ALLOWED_CHANNEL_ID:

            await interaction.response.send_message(
                "❌ لا يمكنك استخدام الأمر هنا.",
                ephemeral=True
            )

            return

        if (
            proof.content_type
            and not proof.content_type.startswith("image/")
        ):

            await interaction.response.send_message(
                "❌ يجب أن يكون الدليل صورة.",
                ephemeral=True
            )

            return

        await interaction.response.defer(
            ephemeral=True
        )

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

        try:

            # إرسال رسالة المخالفة
            violation_message = await interaction.channel.send(
                violation_text
            )

            # إضافة حالة غير مسدد
            await update_violation_status(
                violation_message,
                "unpaid"
            )

            # إنشاء الثريد على نفس رسالة المخالفة
            thread = await violation_message.create_thread(
                name=f"مخالفة - {target.display_name}",
                auto_archive_duration=1440,
                reason="إنشاء ثريد المخالفة"
            )

            # إرسال الأزرار داخل الثريد
            await thread.send(
                view=ViolationView(
                    violation_message.id
                )
            )

            # حفظ البيانات
            users = load_users()

            user_id = str(target.id)

            if user_id not in users:
                users[user_id] = {}

            if "violations" not in users[user_id]:
                users[user_id]["violations"] = []

            users[user_id]["violations"].append({

                "message_id": violation_message.id,

                "thread_id": thread.id,

                "guild_id": interaction.guild.id,

                "channel_id": interaction.channel_id,

                "military_id": interaction.user.id,

                "target_id": target.id,

                "reason": reason,

                "amount": amount,

                "plate": plate,

                "proof": proof.url,

                "status": "unpaid",

                "created_at": datetime.utcnow().isoformat(),

                "due_at": (
                    datetime.utcnow()
                    + timedelta(days=7)
                ).isoformat()

            })

            save_users(users)

            # إرسال رسالة خاصة للمخالف
            try:

                await target.send(
                    "🚨 تم إصدار مخالفة عليك في السيرفر.\n\n"
                    f"**سبب المخالفة:** {reason}\n"
                    f"**مبلغ المخالفة:** {amount}\n"
                    f"**اللوحة:** {plate}\n"
                    f"**الدليل:** {proof.url}"
                )

            except Exception:

                log.info(
                    "Could not DM user %s about violation.",
                    target.id
                )

            await interaction.followup.send(
                "✅ تم إصدار المخالفة بنجاح.",
                ephemeral=True
            )

        except Exception:

            log.exception(
                "Failed to issue violation"
            )

            await interaction.followup.send(
                "❌ حدث خطأ أثناء إصدار المخالفة.",
                ephemeral=True
            )

    # =====================================================
    # فحص المخالفات المتأخرة
    # =====================================================

    @tasks.loop(hours=1)
    async def check_overdue_tickets(self):

        users = load_users()

        changed = False

        now = datetime.utcnow()

        for user_id, user_data in users.items():

            violations = user_data.get(
                "violations",
                []
            )

            for violation in violations:

                if violation.get(
                    "status"
                ) == "paid":

                    continue

                due_at = violation.get(
                    "due_at"
                )

                if not due_at:
                    continue

                try:

                    due_date = datetime.fromisoformat(
                        due_at
                    )

                except Exception:

                    continue

                if now < due_date:
                    continue

                if violation.get(
                    "overdue_handled"
                ):

                    continue

                guild = self.bot.get_guild(
                    violation.get(
                        "guild_id",
                        GUILD_ID
                    )
                )

                if guild is None:
                    continue

                member = guild.get_member(
                    int(user_id)
                )

                if member is not None:

                    role = guild.get_role(
                        OVERDUE_ROLE_ID
                    )

                    if role is not None:

                        try:

                            await member.add_roles(
                                role,
                                reason="مخالفة متأخرة وغير مسددة"
                            )

                        except Exception:

                            log.exception(
                                "Failed to add overdue role to %s",
                                user_id
                            )

                violation[
                    "overdue_handled"
                ] = True

                changed = True

        if changed:
            save_users(users)

    @check_overdue_tickets.before_loop
    async def before_check_overdue_tickets(
        self
    ):

        await self.bot.wait_until_ready()


async def setup(
    bot: commands.Bot
):

    bot.add_dynamic_items(
        ViolationStatusButton
    )

    await bot.add_cog(
        Tickets(bot)
            )
