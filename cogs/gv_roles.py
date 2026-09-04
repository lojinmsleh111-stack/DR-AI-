import discord
from discord import app_commands
from discord.ext import commands

from utils.config import VIOLATION_CHANNEL_ID


# =========================================================
# الإيموجيات
# =========================================================

UNPAID_EMOJI = "<:r_x:1540563530934390866>"
PAID_EMOJI = "<:r_tick:1538664119136161823>"


# =========================================================
# نموذج المخالفة
# =========================================================

def create_violation_text(
    military: discord.Member,
    violator: discord.Member,
    reason: str,
    amount: str,
    plate: str,
    evidence: discord.Attachment,
    extra_evidence: discord.Attachment | None
):
    return (
        "**__تم اصدار مخالفه\n\n"
        f"العسكري : {military.mention}\n\n"
        f"المخالف : {violator.mention}\n\n"
        f"سبب المخالفه : {reason}\n\n"
        f"مبلغ المخالفه : {amount}\n\n"
        f"الوحه : {plate}\n\n"
        f"الدليل : {evidence.url}\n\n"
        f"الدليل الإضافي : "
        f"{extra_evidence.url if extra_evidence else 'لا يوجد'}\n\n\n"
        "..\n\n"
        "__**"
    )


# =========================================================
# تحديث حالة المخالفة
# =========================================================

async def update_violation_status(
    interaction: discord.Interaction,
    emoji: str
):
    thread = interaction.channel

    if not isinstance(thread, discord.Thread):
        return await interaction.response.send_message(
            "❌ الزر يعمل داخل Thread المخالفة فقط.",
            ephemeral=True
        )

    message_id = thread.message_id

    if not message_id:
        return await interaction.response.send_message(
            "❌ لم أستطع العثور على الرسالة الأساسية.",
            ephemeral=True
        )

    parent = thread.parent

    if parent is None:
        return await interaction.response.send_message(
            "❌ لم أستطع العثور على روم المخالفة.",
            ephemeral=True
        )

    try:
        # جلب الرسالة الأساسية التي بدأ منها الـ Thread
        original_message = await parent.fetch_message(message_id)

        content = original_message.content

        # إزالة أي حالة سابقة
        content = content.replace(
            f"\n\n{UNPAID_EMOJI}",
            ""
        )

        content = content.replace(
            f"\n\n{PAID_EMOJI}",
            ""
        )

        # إذا كانت الحالة موجودة بدون فراغين
        content = content.replace(UNPAID_EMOJI, "")
        content = content.replace(PAID_EMOJI, "")

        # إضافة الحالة الجديدة
        new_content = content.rstrip() + f"\n\n{emoji}"

        await original_message.edit(
            content=new_content
        )

        if emoji == PAID_EMOJI:
            message = "تم تسجيل المخالفة كـ تم السداد."
        else:
            message = "تم تسجيل المخالفة كـ لم يتم السداد."

        await interaction.response.send_message(
            message,
            ephemeral=True
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ البوت لا يملك صلاحية تعديل الرسالة.",
            ephemeral=True
        )

    except discord.NotFound:
        await interaction.response.send_message(
            "❌ لم أستطع العثور على الرسالة الأساسية.",
            ephemeral=True
        )

    except discord.HTTPException:
        await interaction.response.send_message(
            "❌ حدث خطأ أثناء تعديل حالة المخالفة.",
            ephemeral=True
        )


# =========================================================
# أزرار السداد
# =========================================================

class ViolationView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    # -----------------------------------------------------
    # تم السداد
    # -----------------------------------------------------

    @discord.ui.button(
        label="تم السداد",
        style=discord.ButtonStyle.success,
        custom_id="violation_paid"
    )
    async def paid(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await update_violation_status(
            interaction,
            PAID_EMOJI
        )

    # -----------------------------------------------------
    # لم يتم السداد
    # -----------------------------------------------------

    @discord.ui.button(
        label="لم يتم السداد",
        style=discord.ButtonStyle.danger,
        custom_id="violation_unpaid"
    )
    async def unpaid(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await update_violation_status(
            interaction,
            UNPAID_EMOJI
        )


# =========================================================
# Violations Cog
# =========================================================

class Violations(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # /mokhalfa
    # =====================================================

    @app_commands.command(
        name="mokhalfa",
        description="إصدار مخالفة"
    )
    @app_commands.describe(
        military="العسكري",
        violator="المخالف",
        reason="سبب المخالفة",
        amount="مبلغ المخالفة",
        plate="اللوحة",
        evidence="الدليل - صورة",
        extra_evidence="الدليل الإضافي - صورة اختيارية"
    )
    async def issue(
        self,
        interaction: discord.Interaction,
        military: discord.Member,
        violator: discord.Member,
        reason: str,
        amount: str,
        plate: str,
        evidence: discord.Attachment,
        extra_evidence: discord.Attachment | None = None
    ):
        await interaction.response.defer(
            ephemeral=True
        )

        # =================================================
        # التأكد من أن الأمر داخل سيرفر
        # =================================================

        if interaction.guild is None:
            return await interaction.followup.send(
                "❌ هذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True
            )

        # =================================================
        # التحقق من الدليل الأساسي
        # =================================================

        if (
            evidence.content_type is None
            or not evidence.content_type.startswith("image/")
        ):
            return await interaction.followup.send(
                "❌ الدليل الأساسي يجب أن يكون صورة.",
                ephemeral=True
            )

        # =================================================
        # التحقق من الدليل الإضافي
        # =================================================

        if (
            extra_evidence is not None
            and (
                extra_evidence.content_type is None
                or not extra_evidence.content_type.startswith("image/")
            )
        ):
            return await interaction.followup.send(
                "❌ الدليل الإضافي يجب أن يكون صورة.",
                ephemeral=True
            )

        # =================================================
        # رومات المخالفات
        # =================================================

        channel_ids = VIOLATION_CHANNEL_ID

        if not isinstance(
            channel_ids,
            (list, tuple, set)
        ):
            channel_ids = [channel_ids]

        channels = []

        for channel_id in channel_ids:

            try:
                channel_id = int(channel_id)
            except (TypeError, ValueError):
                continue

            channel = interaction.guild.get_channel(
                channel_id
            )

            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(
                        channel_id
                    )
                except (
                    discord.NotFound,
                    discord.Forbidden,
                    discord.HTTPException
                ):
                    continue

            if isinstance(
                channel,
                discord.TextChannel
            ):
                if channel.id not in [
                    c.id for c in channels
                ]:
                    channels.append(channel)

        if not channels:
            return await interaction.followup.send(
                "❌ لم أجد رومات المخالفات.",
                ephemeral=True
            )

        # =================================================
        # إنشاء نموذج المخالفة
        # =================================================

        violation_text = create_violation_text(
            military=military,
            violator=violator,
            reason=reason,
            amount=amount,
            plate=plate,
            evidence=evidence,
            extra_evidence=extra_evidence
        )

        sent_messages = []

        # =================================================
        # إرسال المخالفة إلى الرومات
        # =================================================

        for channel in channels:

            try:

                # -----------------------------------------
                # الرسالة الأساسية
                # -----------------------------------------

                # نضع ❌ تلقائيًا عند إنشاء المخالفة
                initial_content = (
                    violation_text.rstrip()
                    + f"\n\n{UNPAID_EMOJI}"
                )

                message = await channel.send(
                    content=initial_content,
                    allowed_mentions=discord.AllowedMentions(
                        users=True
                    )
                )

                sent_messages.append(message)

                # -----------------------------------------
                # مهم:
                # لا نرسل الصور كمرفقات مرة ثانية.
                #
                # روابط الصور موجودة أصلًا داخل النموذج
                # ولذلك لن تتكرر الصورة.
                # -----------------------------------------

                # -----------------------------------------
                # إنشاء Thread
                # -----------------------------------------

                try:

                    thread = await message.create_thread(
                        name=(
                            f"مخالفة - "
                            f"{violator.display_name}"
                        )
                    )

                    await thread.send(
                        "اختر حالة السداد:",
                        view=ViolationView()
                    )

                except (
                    discord.Forbidden,
                    discord.HTTPException
                ):
                    pass

            except (
                discord.Forbidden,
                discord.HTTPException
            ):
                continue

        # =================================================
        # التأكد من نجاح الإرسال
        # =================================================

        if not sent_messages:
            return await interaction.followup.send(
                "❌ لم أستطع إرسال المخالفة إلى أي روم.\n\n"
                "تأكد من صلاحيات البوت:\n"
                "• View Channel\n"
                "• Send Messages\n"
                "• Create Public Threads\n"
                "• Send Messages in Threads",
                ephemeral=True
            )

        # =================================================
        # إرسال نسخة للمخالف بالخاص
        # =================================================

        try:

            await violator.send(
                content=violation_text
            )

            # لا نرسل الدليل كمرفق هنا أيضًا،
            # لأن الرابط موجود داخل النموذج.

        except (
            discord.Forbidden,
            discord.HTTPException
        ):
            pass

        # =================================================
        # تأكيد الأمر
        # =================================================

        await interaction.followup.send(
            "✅ تم إصدار المخالفة وإرسالها إلى "
            f"{len(sent_messages)} روم.",
            ephemeral=True
        )


# =========================================================
# Setup
# =========================================================

async def setup(bot):

    # Persistent View
    bot.add_view(
        ViolationView()
    )

    await bot.add_cog(
        Violations(bot)
    )
