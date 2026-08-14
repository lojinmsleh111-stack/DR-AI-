import asyncio
import json
import logging
import os
import random

import aiohttp
import discord
from discord.ext import commands

logger = logging.getLogger("bot")

# =========================================================
# IDs
# =========================================================

REVIEW_CHANNEL_ID = 1532414607577055465
APPLICATION_LOG_CHANNEL_ID = 1532414637373657169
PASSED_ROLE_ID = 1532414257772101812
ALLOWED_SETUP_ROLE_ID = 1532414187685413055
ROLE_TO_REMOVE_ID = 1532414262343897319

# =========================================================
# Settings
# =========================================================

GROQ_MODEL = "llama-3.3-70b-versatile"
DM_TIMEOUT_SECONDS = 300
IMAGE_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
)


def is_image_attachment(attachment: discord.Attachment) -> bool:
    content_type = (attachment.content_type or "").lower()
    filename = (attachment.filename or "").lower()
    return (
        content_type.startswith("image/")
        or filename.endswith(IMAGE_EXTENSIONS)
    )


def disable_view_buttons(view: discord.ui.View):
    for child in view.children:
        if isinstance(child, discord.ui.Button):
            child.disabled = True


# =========================================================
# Questions
# =========================================================

QUESTIONS = [
    (
        "name",
        "الاسم الكريم :",
        None
    ),
    (
        "age",
        "عمرك الحقيقي :",
        None
    ),
    (
        "roblox_main",
        "اسم حسابك الأساسي في روبلوكس :",
        None
    ),
    (
        "roblox_short",
        "اختصار حسابك في روبلوكس :",
        None
    ),
    (
        "roblox_image",
        "صورة حسابك روبلوكس :",
        None
    ),
    (
        "traffic_fine",
        "؟ كم قيمة مخالفة قطع الإشارة في دارك سيتي :",
        None
    ),
    (
        "pledge",
        "قسم الالتزام بقوانين السيرفر :",
        (
            "انسخ القسم التالي وعبّي اسمك مكان ( اسمك ) وأرسله كما هو:\n\n"
            "** اقسم بالله العظيم انا ( اسمك ) احترم قوانين سيرفر دارك سيتي "
            "واعضائه وما اخرب او اسب وانا على حلفي ووعدي **"
        )
    ),
]
# =========================================================
# Permissions
# =========================================================

def has_review_permission(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True

    role = member.guild.get_role(ALLOWED_SETUP_ROLE_ID)

    return (
        role is not None
        and role in member.roles
    )

# =========================================================
# Application Logs
# =========================================================

async def send_log(
    bot: commands.Bot,
    embed: discord.Embed
):
    channel = bot.get_channel(APPLICATION_LOG_CHANNEL_ID)

    if channel is None:
        try:
            channel = await bot.fetch_channel(
                APPLICATION_LOG_CHANNEL_ID
            )
        except Exception as e:
            logger.warning(
                "Application log channel unavailable: %s",
                e
            )
            return

    if not isinstance(channel, discord.abc.Messageable):
        logger.warning(
            "Application log channel is not messageable: %s",
            type(channel).__name__
        )
        return

    try:
        await channel.send(embed=embed)
    except Exception as e:
        logger.warning(
            "Failed to send application log: %s",
            e
        )

# =========================================================
# Roblox API
# =========================================================

async def check_roblox_username(
    username: str
) -> tuple[bool, str]:

    username = username.strip()

    if not username:
        return False, "اسم Roblox فارغ."

    url = "https://users.roblox.com/v1/usernames/users"

    payload = {
        "usernames": [username],
        "excludeBannedUsers": False
    }

    try:
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            async with session.post(
                url,
                json=payload
            ) as response:

                if response.status != 200:
                    return (
                        False,
                        "تعذر الاتصال بخدمة Roblox حالياً."
                    )

                data = await response.json()

                users = data.get("data", [])

                if not users:
                    return (
                        False,
                        "حساب Roblox غير موجود."
                    )

                roblox_name = users[0].get("name")

                if not roblox_name:
                    return (
                        False,
                        "تعذر الحصول على اسم حساب Roblox."
                    )

                return True, roblox_name

    except asyncio.TimeoutError:
        return (
            False,
            "انتهى وقت الاتصال بخدمة Roblox."
        )

    except aiohttp.ClientError:
        return (
            False,
            "حدث خطأ أثناء الاتصال بخدمة Roblox."
        )

    except Exception as e:
        logger.exception(
            "Roblox API error: %s",
            e
        )

        return (
            False,
            "حدث خطأ غير متوقع أثناء التحقق من حساب Roblox."
        )

# =========================================================
# Traffic fine question
# =========================================================

class TrafficFineSelect(discord.ui.Select):
    def __init__(self, view: "TrafficFineView"):
        self.fine_view = view

        options = [
            discord.SelectOption(
                label="3000",
                value="3000"
            ),
            discord.SelectOption(
                label="2500",
                value="2500"
            ),
            discord.SelectOption(
                label="2000",
                value="2000"
            ),
        ]

        super().__init__(
            placeholder="اختر قيمة المخالفة...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="dr_apply_fine_select"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):
        await self.fine_view._choose(
            interaction,
            self.values[0]
        )


class TrafficFineView(discord.ui.View):
    """Select menu with a maximum of two attempts."""

    def __init__(self, applicant_id: int):
        super().__init__(timeout=DM_TIMEOUT_SECONDS)

        self.applicant_id = applicant_id
        self.attempts = 0
        self.answer = None

        self.add_item(
            TrafficFineSelect(self)
        )

    async def _choose(
        self,
        interaction: discord.Interaction,
        value: str
    ):
        if interaction.user.id != self.applicant_id:
            await interaction.response.send_message(
                "❌ هذه الاختيارات ليست مخصصة لك.",
                ephemeral=True
            )
            return

        self.attempts += 1

        if value == "3000":
            self.answer = value

            for child in self.children:
                child.disabled = True

            await interaction.response.edit_message(
                view=self
            )

            self.stop()
            return

        if self.attempts == 1:
            await interaction.response.send_message(
                "❌ إجابتك خاطئة، لديك محاولة أخيرة.",
                ephemeral=True
            )
            return

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content="❌ أخطأت في المحاولتين، تم رفض طلب التصريح.",
            view=self
        )

        self.stop()
# =========================================================
# AI Evaluation
# =========================================================

async def evaluate_application_ai(
    answers: dict
) -> dict:

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        return {
            "decision": "manual_review",
            "reason": "مفتاح GROQ_API_KEY غير موجود."
        }

    try:
        from groq import AsyncGroq
    except ImportError:
        return {
            "decision": "manual_review",
            "reason": "مكتبة groq غير مثبتة."
        }

    prompt = f"""
أنت مشرف يراجع طلبات رول بلاي.

مهم جداً:
العمر تم التحقق منه برمجياً مسبقاً.
لا تحاول الحكم على العمر.

القرارات المسموحة فقط:

accept
reject
manual_review

accept:
إذا كانت الإجابات جادة ومنطقية.

reject:
إذا كانت الإجابات غير لائقة أو عشوائية أو مخالفة.

manual_review:
إذا كان هناك شك.

أجب JSON فقط.

الاسم:
{answers.get("name")}

العمر:
{answers.get("age")}

Roblox:
{answers.get("roblox_main")}

اختصار Roblox:
{answers.get("roblox_short")}

قيمة مخالفة قطع الإشارة:
{answers.get("traffic_fine")}

عدد محاولات السؤال السادس:
{answers.get("traffic_attempts")}

التعهد:
{answers.get("pledge")}

الصيغة:

{{
    "decision": "accept",
    "reason": "سبب مختصر بالعربي"
}}
"""

    try:
        client = AsyncGroq(api_key=api_key)

        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            max_tokens=300,
            temperature=0.2,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        text = (
            response
            .choices[0]
            .message
            .content
            or ""
        ).strip()

        text = (
            text
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        data = json.loads(text)

        if data.get("decision") not in {
            "accept",
            "reject",
            "manual_review"
        }:
            raise ValueError("Invalid AI decision")

        return data

    except Exception as e:
        logger.exception(
            "AI evaluation failed: %s",
            e
        )

        return {
            "decision": "manual_review",
            "reason": (
                "تعذر التحليل الآلي، "
                "يحتاج الطلب مراجعة يدوية."
            )
        }

# =========================================================
# Review Buttons
# =========================================================

class RPReviewButtons(discord.ui.View):

    def __init__(
        self,
        applicant_id: int,
        roblox_name: str,
        cog: "ApplyCog",
        answers: dict | None = None
    ):
        super().__init__(timeout=None)

        self.applicant_id = applicant_id
        self.roblox_name = roblox_name
        self.cog = cog
        self.answers = answers or {}

    async def _allowed(
        self,
        interaction: discord.Interaction
    ) -> bool:

        if (
            not interaction.guild
            or not isinstance(
                interaction.user,
                discord.Member
            )
        ):
            await interaction.response.send_message(
                "❌ هذا الزر يعمل داخل السيرفر فقط.",
                ephemeral=True
            )
            return False

        if not has_review_permission(
            interaction.user
        ):
            await interaction.response.send_message(
                "❌ لا تملك صلاحية القيام بهذا الإجراء.",
                ephemeral=True
            )
            return False

        return True

    @discord.ui.button(
        label="✅ قبول الطلب",
        style=discord.ButtonStyle.success,
        custom_id="dr_apply_accept"
    )
    async def accept(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not await self._allowed(interaction):
            return

        disable_view_buttons(self)

        button.label = "✅ تم القبول"

        await interaction.response.edit_message(
            view=self
        )

        await self.cog.finalize_application(
            self.applicant_id,
            self.roblox_name,
            True,
            interaction.user.display_name,
            "قرار يدوي من الإدارة",
            self.answers
        )

    @discord.ui.button(
        label="❌ رفض الطلب",
        style=discord.ButtonStyle.danger,
        custom_id="dr_apply_reject"
    )
    async def reject(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not await self._allowed(interaction):
            return

        disable_view_buttons(self)

        button.label = "❌ تم الرفض"

        await interaction.response.edit_message(
            view=self
        )

        await self.cog.finalize_application(
            self.applicant_id,
            self.roblox_name,
            False,
            interaction.user.display_name,
            "قرار يدوي من الإدارة",
            self.answers
        )

# =========================================================
# Start Application View
# =========================================================

class ApplyStartView(discord.ui.View):

    def __init__(
        self,
        cog: "ApplyCog"
    ):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="تقديم طلب تصريح رول بلاي",
        style=discord.ButtonStyle.blurple,
        emoji="👾",
        custom_id="dr_apply_start"
    )
    async def start_apply(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        user_id = interaction.user.id

        if user_id in self.cog.pending_applicants:
            await interaction.response.send_message(
                "⏳ عندك طلب قيد التقديم حالياً.",
                ephemeral=True
            )
            return

        self.cog.pending_applicants.add(user_id)

        try:

            await interaction.response.send_message(
                "📩 شيك الخاص، أرسلتلك الأسئلة هناك!",
                ephemeral=True
            )

            try:

                await interaction.user.send(
                    "📝 أهلاً بك!\n"
                    "رح أرسلك الأسئلة وحدة وحدة."
                )

            except discord.Forbidden:

                self.cog.pending_applicants.discard(
                    user_id
                )

                await interaction.followup.send(
                    "❌ الخاص عندك مقفل. "
                    "افتح الرسائل الخاصة وحاول مرة ثانية.",
                    ephemeral=True
                )

                return

            asyncio.create_task(
                self.cog.run_dm_interview(
                    interaction.user
                )
            )

        except Exception as e:

            self.cog.pending_applicants.discard(
                user_id
            )

            logger.exception(
                "Start application failed: %s",
                e
            )

# =========================================================
# Apply Cog
# =========================================================

class ApplyCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.pending_applicants: set[int] = set()

    async def cog_load(self):

        self.bot.add_view(
            ApplyStartView(self)
        )

        self.bot.add_view(
            RPReviewButtons(
                0,
                "",
                self
            )
        )

    # =====================================================
    # Setup Panel Command
    # =====================================================

    @commands.hybrid_command(
        name="setup_apply",
        description="إنشاء لوحة تقديم تصريح الرول بلاي"
    )
    async def setup_apply(
        self,
        ctx: commands.Context
    ):

        if (
            not isinstance(
                ctx.author,
                discord.Member
            )
            or not has_review_permission(
                ctx.author
            )
        ):

            await ctx.send(
                "❌ لا تملك صلاحية إنشاء لوحة التصريح."
            )

            return

        embed = discord.Embed(
            title="🎮 طلب تصريح دخول الرول بلاي",
            description=(
                "أهلاً بك في السيرفر!\n\n"
                "اضغط على الزر بالأسفل "
                "وسيتم إرسال الأسئلة لك في الخاص."
            ),
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text="إدارة سيرفر دارك سيتي 📗"
        )

        await ctx.send(
            embed=embed,
            view=ApplyStartView(self)
        )

    # =====================================================
    # Interview
    # =====================================================

    async def run_dm_interview(
        self,
        user: discord.User | discord.Member
    ):

        answers = {}

        def check(message: discord.Message):

            return (
                message.author.id == user.id
                and isinstance(
                    message.channel,
                    discord.DMChannel
                )
            )

        try:

            for (
                key,
                title,
                description
            ) in QUESTIONS:

                embed = discord.Embed(
                    title=title,
                    description=description,
                    color=discord.Color.blurple()
                )

                embed.set_footer(
                    text="إدارة سيرفر دارك سيتي 📗"
                )

                await user.send(
                    embed=embed
                )

                if key == "traffic_fine":
                    fine_view = TrafficFineView(user.id)
                    await user.send(view=fine_view)
                    timed_out = await fine_view.wait()

                    answers["traffic_attempts"] = fine_view.attempts

                    if fine_view.answer is None:
                        if fine_view.attempts >= 2:
                            answers["traffic_fine"] = "إجابة خاطئة"
                            await self.finalize_application(
                                user.id,
                                answers.get("roblox_main", "Unknown"),
                                False,
                                "نظام التحقق",
                                "تم رفض الطلب بعد استنفاد محاولتي السؤال السادس.",
                                answers
                            )
                        elif timed_out:
                            await user.send(
                                "⌛ انتهى الوقت المسموح للرد.\n"
                                "قدم الطلب من جديد."
                            )
                        return

                    answers["traffic_fine"] = fine_view.answer
                    continue

                if key == "roblox_image":
                    while True:
                        message = await self.bot.wait_for(
                            "message",
                            check=check,
                            timeout=DM_TIMEOUT_SECONDS
                        )

                        if not message.attachments:
                            await user.send(
                                "❌ يجب إرسال صورة لحساب Roblox كمرفق."
                            )
                            continue

                        image_attachments = [
                            attachment
                            for attachment in message.attachments
                            if is_image_attachment(attachment)
                        ]

                        if (
                            not image_attachments
                            or len(image_attachments) != len(message.attachments)
                        ):
                            await user.send(
                                "❌ الملف المرسل ليس صورة. "
                                "أرسل صورة لحساب Roblox فقط."
                            )
                            continue

                        answers[key] = image_attachments[0].url
                        break

                    continue

                message = await self.bot.wait_for(
                    "message",
                    check=check,
                    timeout=DM_TIMEOUT_SECONDS
                )

                answer = message.content.strip()

                # =========================================
                # AGE FIX
                # =========================================

                if key == "age":

                    if not answer.isdigit():

                        await user.send(
                            "❌ لو سمحت أدخل عمرك بالأرقام فقط.\n"
                            "مثال: `14`"
                        )

                        return

                    age = int(answer)

                    # أقل من 10 = رفض
                    # 10 أو أكثر = مسموح
                    if age < 10:

                        await user.send(
                            "❌ عذراً، يجب أن يكون عمرك "
                            "10 سنوات أو أكثر."
                        )

                        return

                    if age > 80:

                        await user.send(
                            "❌ الرجاء إدخال عمر صحيح."
                        )

                        return

                # =========================================
                # ROBLOX
                # =========================================

                if key == "roblox_main":

                    checking = await user.send(
                        "🔎 جاري التحقق من حساب Roblox، "
                        "لو سمحت انتظر..."
                    )

                    exists, result = (
                        await check_roblox_username(
                            answer
                        )
                    )

                    if not exists:

                        await checking.edit(
                            content=(
                                f"❌ لم يتم العثور على حساب "
                                f"Roblox باسم `{answer}`.\n"
                                f"{result}"
                            )
                        )

                        return

                    answers[key] = result

                    await checking.edit(
                        content=(
                            f"✅ تم العثور على حساب Roblox: "
                            f"`{result}`"
                        )
                    )

                    continue

                answers[key] = answer

        except asyncio.TimeoutError:

            await user.send(
                "⌛ انتهى الوقت المسموح للرد.\n"
                "قدم الطلب من جديد."
            )

            return

        except discord.Forbidden:
            return

        except Exception as e:

            logger.exception(
                "Application interview failed: %s",
                e
            )

            try:

                await user.send(
                    "❌ حدث خطأ أثناء الطلب. "
                    "حاول مرة أخرى لاحقاً."
                )

            except Exception:
                pass

            return

        finally:

            self.pending_applicants.discard(
                user.id
            )

        await user.send(
            "✅ تم استلام إجاباتك.\n"
            "جاري تحليل الطلب..."
        )

        ai_result = await evaluate_application_ai(
            answers
        )

        decision = ai_result.get(
            "decision",
            "manual_review"
        )

        reason = ai_result.get(
            "reason",
            ""
        )

        if decision == "manual_review":

            await self.send_for_manual_review(
                user,
                answers,
                reason
            )

        else:

            await self.finalize_application(
                user.id,
                answers.get(
                    "roblox_main",
                    "Unknown"
                ),
                decision == "accept",
                "🤖 الذكاء الاصطناعي",
                reason,
                answers
            )

    # =====================================================
    # Manual Review
    # =====================================================

    async def send_for_manual_review(
        self,
        user,
        answers,
        reason=""
    ):

        channel = self.bot.get_channel(
            REVIEW_CHANNEL_ID
        )

        if channel is None:

            try:

                channel = await self.bot.fetch_channel(
                    REVIEW_CHANNEL_ID
                )

            except Exception as e:

                logger.warning(
                    "Review channel unavailable: %s",
                    e
                )

                return

        embed = discord.Embed(
            title="📑 طلب تصريح رول بلاي - مراجعة",
            color=discord.Color.gold()
        )

        embed.set_thumbnail(
            url=user.display_avatar.url
        )

        embed.add_field(
            name="👤 العضو",
            value=(
                f"{user.mention} "
                f"(`{user.id}`)"
            ),
            inline=False
        )

        embed.add_field(
            name="الاسم الكريم :",
            value=answers.get(
                "name",
                "-"
            ),
            inline=False
        )

        embed.add_field(
            name="العمر :",
            value=answers.get(
                "age",
                "-"
            ),
            inline=True
        )

        embed.add_field(
            name="اسم حساب Roblox :",
            value=(
                f"`{answers.get('roblox_main', '-')}`"
            ),
            inline=True
        )

        embed.add_field(
            name="اختصار Roblox :",
            value=(
                f"`{answers.get('roblox_short', '-')}`"
            ),
            inline=True
        )

        embed.add_field(
            name="صورة حساب Roblox :",
            value=(
                f"[فتح الصورة]({answers.get('roblox_image', '-')})"
                if answers.get("roblox_image")
                else "-"
            ),
            inline=False
        )

        embed.add_field(
            name="قيمة مخالفة قطع الإشارة :",
            value=answers.get("traffic_fine", "-"),
            inline=True
        )

        embed.add_field(
            name="عدد محاولات السؤال السادس :",
            value=str(answers.get("traffic_attempts", "-")),
            inline=True
        )

        embed.add_field(
            name="قسم الالتزام بقوانين السيرفر :",
            value=answers.get("pledge", "-"),
            inline=False
        )

        if answers.get("roblox_image"):
            embed.set_image(url=answers["roblox_image"])

        if reason:

            embed.add_field(
                name="📝 سبب المراجعة :",
                value=reason[:1024],
                inline=False
            )

        await channel.send(
            embed=embed,
            view=RPReviewButtons(
                user.id,
                answers.get(
                    "roblox_main",
                    "Unknown"
                ),
                self,
                answers
            )
        )

    # =====================================================
    # Finalize
    # =====================================================

    async def finalize_application(
        self,
        applicant_id,
        roblox_name,
        accepted,
        decided_by,
        reason="",
        answers: dict | None = None
    ):
        answers = answers or {}


        guild = None

        for server in self.bot.guilds:

            if server.get_member(applicant_id):

                guild = server
                break

        member = (
            guild.get_member(applicant_id)
            if guild
            else None
        )

        random_id = None
        new_nickname = None

        # =================================================
        # ACCEPT
        # =================================================

        if accepted and guild and member:

            # رقم عشوائي من 6 أرقام
            random_id = random.randint(
                100000,
                999999
            )

            # Discord nickname max = 32
            max_roblox_length = (
                32
                - len("DR |  | ")
                - 6
            )

            roblox_name = roblox_name[
                :max_roblox_length
            ]

            new_nickname = (
                f"DR | {roblox_name} | {random_id}"
            )

            # =============================================
            # Remove old role
            # =============================================

            old_role = guild.get_role(
                ROLE_TO_REMOVE_ID
            )

            if (
                old_role
                and old_role in member.roles
            ):

                try:

                    await member.remove_roles(
                        old_role,
                        reason=(
                            "تم قبول تصريح الرول بلاي"
                        )
                    )

                except Exception as e:

                    logger.warning(
                        "Could not remove old role: %s",
                        e
                    )

            # =============================================
            # Add accepted role
            # =============================================

            passed_role = guild.get_role(
                PASSED_ROLE_ID
            )

            if passed_role:

                try:

                    await member.add_roles(
                        passed_role,
                        reason=(
                            "تم قبول تصريح الرول بلاي"
                        )
                    )

                except Exception as e:

                    logger.warning(
                        "Could not add passed role: %s",
                        e
                    )

            # =============================================
            # Change nickname
            # =============================================

            try:

                await member.edit(
                    nick=new_nickname,
                    reason=(
                        "تم قبول تصريح الرول بلاي"
                    )
                )

            except Exception as e:

                logger.warning(
                    "Could not change nickname: %s",
                    e
                )

            # =============================================
            # DM
            # =============================================

            try:

                await member.send(
                    "🎉 **تم قبول طلبك!**\n\n"
                    f"🎮 حساب Roblox: `{roblox_name}`\n"
                    f"🆔 رقمك: `{random_id}`\n"
                    f"👤 اسمك الجديد: `{new_nickname}`"
                )

            except Exception:
                pass

        # =================================================
        # REJECT
        # =================================================

        elif not accepted and member:

            try:

                await member.send(
                    "❌ **تم رفض طلب تصريح الرول بلاي.**\n\n"
                    f"📝 السبب: "
                    f"{reason or 'قرار الإدارة'}"
                )

            except Exception:
                pass

        # =================================================
        # LOG
        # =================================================

        embed = discord.Embed(
            title=(
                "📜 قبول تصريح"
                if accepted
                else
                "📕 رفض تصريح"
            ),
            color=(
                discord.Color.green()
                if accepted
                else
                discord.Color.red()
            )
        )

        embed.add_field(
            name="👤 العضو",
            value=(
                f"<@{applicant_id}> "
                f"(`{applicant_id}`)"
            ),
            inline=False
        )

        embed.add_field(
            name="👮 بواسطة",
            value=decided_by,
            inline=True
        )

        embed.add_field(
            name="الاسم الكريم :",
            value=str(answers.get("name", "-")),
            inline=False
        )

        embed.add_field(
            name="العمر :",
            value=str(answers.get("age", "-")),
            inline=True
        )

        embed.add_field(
            name="اسم حساب Roblox :",
            value=f"`{answers.get('roblox_main', roblox_name or '-')}`",
            inline=True
        )

        embed.add_field(
            name="اختصار Roblox :",
            value=f"`{answers.get('roblox_short', '-')}`",
            inline=True
        )

        image_url = answers.get("roblox_image")
        embed.add_field(
            name="صورة حساب Roblox :",
            value=f"[فتح الصورة]({image_url})" if image_url else "-",
            inline=False
        )

        embed.add_field(
            name="قيمة مخالفة قطع الإشارة :",
            value=str(answers.get("traffic_fine", "-")),
            inline=True
        )

        embed.add_field(
            name="عدد محاولات السؤال السادس :",
            value=str(answers.get("traffic_attempts", "-")),
            inline=True
        )

        embed.add_field(
            name="قسم الالتزام بقوانين السيرفر :",
            value=str(answers.get("pledge", "-")),
            inline=False
        )

        if image_url:
            embed.set_image(url=image_url)

        if accepted:

            embed.add_field(
                name="🎮 Roblox",
                value=f"`{roblox_name}`",
                inline=True
            )

            embed.add_field(
                name="🆔 RP ID",
                value=f"`{random_id}`",
                inline=True
            )

            embed.add_field(
                name="👤 الاسم الجديد",
                value=f"`{new_nickname}`",
                inline=False
            )

        if reason:

            embed.add_field(
                name="📝 السبب",
                value=reason[:1024],
                inline=False
            )

        await send_log(
            self.bot,
            embed
        )


# =========================================================
# Discord Extension Setup
# =========================================================

async def setup(bot):

    await bot.add_cog(
        ApplyCog(bot)
)
     
