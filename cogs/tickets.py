import discord
from discord.ext import commands, tasks
import json
import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("bot")

# =========================
# IDs - DR-AI
# =========================

USERS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "users.json"
)

TICKET_ALLOWED_CHANNEL_ID = 1532414607577055465
PAYMENT_OFFICER_ROLE_ID = 1532414219843276820
STAFF_ROLE_ID = 1532414219843276820
OVERDUE_ROLE_ID = 1533068412547497984
GUILD_ID = 1532390688187220159

# =========================
# Emojis
# =========================

PAID_EMOJI_ID = 1537811911054196877
UNPAID_EMOJI_ID = 1537811948027117599


# =========================
# Users JSON
# =========================

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


# =========================
# Update Original Violation
# =========================

async def update_violation_status(
    interaction: discord.Interaction,
    message_id: int,
    emoji_id: int
):
    try:
        guild = interaction.guild

        if guild is None:
            return False

        channel = guild.get_channel(TICKET_ALLOWED_CHANNEL_ID)

        if channel is None:
            return False

        try:
            message = await channel.fetch_message(message_id)
        except Exception:
            return False

        bot_user = guild.me

        # Remove old status emojis added by the bot
        for reaction in message.reactions:
            if isinstance(reaction.emoji, discord.Emoji):
                if reaction.emoji.id in (
                    PAID_EMOJI_ID,
                    UNPAID_EMOJI_ID
                ):
                    try:
                        await message.remove_reaction(
                            reaction.emoji,
                            bot_user
                        )
                    except Exception:
                        pass

        # Get new emoji
        emoji = guild.get_emoji(emoji_id)

        if emoji is None:
            try:
                emoji = await guild.fetch_emoji(emoji_id)
            except Exception:
                return False

        # Add new status
        await message.add_reaction(emoji)

        return True

    except Exception as e:
        logger.error(
            f"Error updating violation status: {e}"
        )
        return False


# =========================
# Violation Status Button
# =========================

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
        # Acknowledge immediately
        await interaction.response.defer(
            ephemeral=True
        )

        # Only authorized officers
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

        users = load_users()

        # Find the violation by message ID
        found_ticket = None

        for user_id, data in users.items():
            tickets = data.get("tickets", [])

            for index, ticket in enumerate(tickets):
                if ticket.get("message_id") == self.message_id:
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

        # Update JSON status
        if self.status == "paid":
            ticket["paid"] = True
        else:
            ticket["paid"] = False

        save_users(users)

        # Update original violation message emoji
        updated = await update_violation_status(
            interaction,
            self.message_id,
            PAID_EMOJI_ID
            if self.status == "paid"
            else UNPAID_EMOJI_ID
        )

        if not updated:
            return await interaction.followup.send(
                "⚠️ تم تحديث حالة المخالفة، لكن تعذر تحديث الإيموجي في رسالة المخالفة الأصلية.",
                ephemeral=True
            )

        if self.status == "paid":
            await interaction.followup.send(
                "✅ تم تسجيل المخالفة كـ **تم السداد** وتحديث الإيموجي في رسالة المخالفة الأصلية.",
                ephemeral=True
            )

            # Remove overdue role if all fines are paid
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

        else:
            await interaction.followup.send(
                "🔴 تم تسجيل المخالفة كـ **لم يتم السداد** وتحديث الإيموجي في رسالة المخالفة الأصلية.",
                ephemeral=True
            )


# =========================
# Violation View
# =========================

class ViolationView(discord.ui.View):

    def __init__(self, message_id: int):
        super().__init__(timeout=None)

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


# =========================
# Fine Select
# =========================

class FineSelect(discord.ui.Select):

    def __init__(
        self,
        target_member: discord.Member,
        rp_id: str,
        proof_url: str
    ):
        self.target_member = target_member
        self.rp_id = rp_id
        self.proof_url = proof_url

        options = [
            discord.SelectOption(
                label="سرعة زائدة",
                description="الغرامة: 500 داركي",
                value="500|سرعة زائدة"
            ),
            discord.SelectOption(
                label="قطع الإشارة",
                description="الغرامة: 3000 داركي",
                value="3000|قطع الإشارة"
            ),
            discord.SelectOption(
                label="إزالة لوحة (حجز)",
                description="الغرامة: 2000 داركي",
                value="2000|إزالة لوحة (حجز)"
            ),
            discord.SelectOption(
                label="عدم إضاءة النور أثناء الليل",
                description="الغرامة: 300 داركي",
                value="300|عدم إضاءة النور أثناء الليل"
            ),
            discord.SelectOption(
                label="عدم الالتزام بالمسار",
                description="الغرامة: 400 داركي",
                value="400|عدم الالتزام بالمسار"
            ),
            discord.SelectOption(
                label="إزعاج بدون سبب (حجز)",
                description="الغرامة: 700 داركي",
                value="700|إزعاج بدون سبب (حجز)"
            ),
            discord.SelectOption(
                label="وقوف وسط الطريق (حجز)",
                description="الغرامة: 1000 داركي",
                value="1000|وقوف وسط الطريق (حجز)"
            ),
            discord.SelectOption(
                label="عدم إفساح الطريق لمركبات الطوارئ",
                description="الغرامة: 200 داركي",
                value="200|عدم إفساح الطريق لمركبات الطوارئ"
            ),
            discord.SelectOption(
                label="تعديل بدون تصريح (حجز/حرمان)",
                description="الغرامة: 10000 داركي",
                value="10000|تعديل بدون تصريح (حجز)"
            ),
            discord.SelectOption(
                label="تفحيط (حجز)",
                description="الغرامة: 5000 داركي",
                value="5000|تفحيط (حجز)"
            ),
            discord.SelectOption(
                label="زرة (حجز)",
                description="الغرامة: 2000 داركي",
                value="2000|زرة (حجز)"
            ),
        ]

        super().__init__(
            placeholder="📋 اختر نوع المخالفة المرورية...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):
        await interaction.response.defer(
            ephemeral=True
        )

        amount, reason = self.values[0].split("|")
        amount = int(amount)

        users = load_users()
        user_key = str(self.target_member.id)

        if user_key not in users:
            users[user_key] = {
                "discord_tag": str(
                    self.target_member
                ),
                "real_name": self.target_member.display_name,
                "rp_id": self.rp_id,
                "tickets": [],
                "permits": []
            }

        if "tickets" not in users[user_key]:
            users[user_key]["tickets"] = []

        now_str = datetime.now().isoformat()

        ticket_data = {
            "amount": amount,
            "reason": reason,
            "issuer": interaction.user.display_name,
            "issued_at": now_str,
            "paid": False,

            # فقط الدليل الأساسي
            "proof_url": self.proof_url,

            # سيتم تعبئته بعد إرسال الرسالة
            "message_id": None
        }

        users[user_key]["tickets"].append(
            ticket_data
        )

        save_users(users)

        ticket_index = len(
            users[user_key]["tickets"]
        ) - 1

        # =========================
        # Violation Embed
        # =========================

        embed = discord.Embed(
            title="🚔 وزارة الداخلية - إشعار مخالفة مرورية",
            description=(
                f"تم إدخال مخالفة مرورية جديدة "
                f"بحق المواطن {self.target_member.mention}."
            ),
            color=0xe74c3c
        )

        embed.add_field(
            name="👤 المواطن المخالف",
            value=self.target_member.mention,
            inline=True
        )

        embed.add_field(
            name="🆔 رقم الهوية المرورية",
            value=f"`{self.rp_id}`",
            inline=True
        )

        embed.add_field(
            name="💰 قيمة الغرامة",
            value=f"**{amount:,} داركي**",
            inline=True
        )

        embed.add_field(
            name="📝 نوع المخالفة",
            value=f"`{reason}`",
            inline=False
        )

        embed.add_field(
            name="👮‍♂️ العسكري المحرر",
            value=(
                f"{interaction.user.mention} "
                f"(`{interaction.user.display_name}`)"
            ),
            inline=False
        )

        # الدليل الأساسي فقط
        embed.set_image(
            url=self.proof_url
        )

        embed.add_field(
            name="🔴 ملاحظات هامة",
            value=(
                "• جهلك بالقوانين لا يرفع عنك العقوبة.\n"
                "• المخالفات وُضعت للحفاظ على سلامتكم من خطر الطريق.\n"
                "• ⚠️ **مهلة التسديد هي 7 أيام**، وفي حال عدم التسديد سيتم **إيقاف خدماتك** تلقائياً.\n"
                "• في حال محاولة الهروب سيتم تحويلك للسجن مباشرة."
            ),
            inline=False
        )

        embed.set_footer(
            text="وزارة الداخلية تتمنى لكم قيادة آمنة وسعيدة 📗"
        )

        traffic_channel = interaction.guild.get_channel(
            TICKET_ALLOWED_CHANNEL_ID
        )

        if traffic_channel is None:
            return await interaction.followup.send(
                "❌ لم يتم العثور على روم المخالفات.",
                ephemeral=True
            )

        # =========================
        # Send Original Violation
        # =========================

        message = await traffic_channel.send(
            content=(
                f"📢 إشعار مخالفة موجه للمواطن: "
                f"{self.target_member.mention}"
            ),
            embed=embed
        )

        # Save original message ID
        users[user_key]["tickets"][ticket_index][
            "message_id"
        ] = message.id

        save_users(users)

        # =========================
        # Initial Unpaid Emoji
        # =========================

        unpaid_emoji = interaction.guild.get_emoji(
            UNPAID_EMOJI_ID
        )

        if unpaid_emoji:
            try:
                await message.add_reaction(
                    unpaid_emoji
                )
            except Exception:
                pass

        # =========================
        # Create Thread
        # =========================

        try:
            thread = await message.create_thread(
                name=(
                    f"مخالفة - "
                    f"{self.target_member.display_name}"
                )
            )

            await thread.send(
                content=(
                    "📋 **حالة سداد المخالفة**\n"
                    "استخدم الأزرار بالأسفل لتحديث حالة السداد."
                ),
                view=ViolationView(message.id)
            )

        except Exception as e:
            logger.error(
                f"Error creating violation thread: {e}"
            )

        # =========================
        # DM Citizen
        # =========================

        try:
            await self.target_member.send(
                embed=embed
            )
        except discord.Forbidden:
            pass

        await interaction.followup.send(
            content=(
                f"✅ تم تحرير المخالفة وإرسالها "
                f"للمواطن {self.target_member.mention} بنجاح!"
            ),
            ephemeral=True
        )


# =========================
# Fine View
# =========================

class FineView(discord.ui.View):

    def __init__(
        self,
        target_member: discord.Member,
        rp_id: str,
        proof_url: str
    ):
        super().__init__(timeout=60)

        self.add_item(
            FineSelect(
                target_member,
                rp_id,
                proof_url
            )
        )


# =========================
# Tickets Cog
# =========================

class TicketsCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.check_overdue_tickets.start()

    def cog_unload(self):
        self.check_overdue_tickets.cancel()

    # =========================
    # /مخالفة
    # =========================

    @discord.app_commands.command(
        name="مخالفة",
        description="تحرير مخالفة مرورية لمواطن"
    )
    async def make_ticket(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        proof: discord.Attachment
    ):

        # Correct channel
        if interaction.channel_id != TICKET_ALLOWED_CHANNEL_ID:
            allowed_channel = interaction.guild.get_channel(
                TICKET_ALLOWED_CHANNEL_ID
            )

            channel_mention = (
                allowed_channel.mention
                if allowed_channel
                else f"<#{TICKET_ALLOWED_CHANNEL_ID}>"
            )

            return await interaction.response.send_message(
                (
                    "❌ **عفواً، لا يمكنك استخدام هذا الأمر هنا!**\n"
                    f"يرجى استخدام الأمر في الروم المخصصة فقط: "
                    f"{channel_mention}"
                ),
                ephemeral=True
            )

        # Staff permission
        staff_role = interaction.guild.get_role(
            STAFF_ROLE_ID
        )

        if (
            staff_role not in interaction.user.roles
            and not interaction.user.guild_permissions.administrator
        ):
            return await interaction.response.send_message(
                "❌ هذا الأمر مخصص لرجال الشرطة والإدارة فقط.",
                ephemeral=True
            )

        # Basic evidence only
        if (
            not proof.content_type
            or not proof.content_type.startswith("image/")
        ):
            return await interaction.response.send_message(
                "❌ يجب إرفاق صورة دليل صالحة للمخالفة!",
                ephemeral=True
            )

        users = load_users()

        user_data = users.get(
            str(target.id)
        )

        rp_id = (
            user_data.get("rp_id", "غير مسجل")
            if user_data
            else "غير مسجل"
        )

        view = FineView(
            target,
            rp_id,
            proof.url
        )

        await interaction.response.send_message(
            content=(
                f"👮‍♂️ جاري تحرير مخالفة للمواطن: "
                f"{target.mention} "
                f"(الهوية: `{rp_id}`)\n"
                "اختر نوع المخالفة من القائمة:"
            ),
            view=view,
            ephemeral=True
        )

    # =========================
    # Overdue System
    # =========================

    @tasks.loop(hours=1)
    async def check_overdue_tickets(self):

        guild = self.bot.get_guild(
            GUILD_ID
        )

        if not guild:
            return

        overdue_role = guild.get_role(
            OVERDUE_ROLE_ID
        )

        if not overdue_role:
            return

        users = load_users()
        now = datetime.now()

        for user_id_str, data in users.items():

            tickets = data.get(
                "tickets",
                []
            )

            has_unpaid_overdue = False

            for ticket in tickets:

                if not ticket.get(
                    "paid",
                    False
                ):

                    issued_at_str = ticket.get(
                        "issued_at"
                    )

                    if issued_at_str:

                        try:
                            issued_at = datetime.fromisoformat(
                                issued_at_str
                            )

                            if (
                                now - issued_at
                                >= timedelta(days=7)
                            ):
                                has_unpaid_overdue = True
                                break

                        except Exception:
                            pass

            if has_unpaid_overdue:

                try:

                    member = guild.get_member(
                        int(user_id_str)
                    )

                    if (
                        member
                        and overdue_role not in member.roles
                    ):

                        await member.add_roles(
                            overdue_role
                        )

                        try:

                            embed_warn = discord.Embed(
                                title="⚠️ إشعار إيقاف خدمات",
                                description=(
                                    "لقد انقضت مهلة الـ 7 أيام "
                                    "لتسديد مخالفاتك المرورية دون تسديدها.\n"
                                    "تم تطبيق **إيقاف الخدمات** عليك "
                                    "في السيرفر، يرجى التوجه لإدارة المرور "
                                    "لتسوية وضعك وفك الإيقاف."
                                ),
                                color=discord.Color.dark_red()
                            )

                            await member.send(
                                embed=embed_warn
                            )

                        except Exception:
                            pass

                except Exception as e:

                    logger.error(
                        f"خطأ أثناء منح رتبة إيقاف الخدمات: {e}"
                    )


# =========================
# Setup
# =========================

async def setup(bot):

    # Dynamic buttons
    bot.add_dynamic_items(
        ViolationStatusButton
    )

    await bot.add_cog(
        TicketsCog(bot)
    )
