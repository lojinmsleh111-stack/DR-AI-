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

# روم المخالفات / مراجعة طلبات التصريح
REVIEW_CHANNEL_ID = 1532414607577055465

# روم لوق التصاريح
APPLICATION_LOG_CHANNEL_ID = 1532414637373657169

# رتبة القبول
PASSED_ROLE_ID = 1532414257772101812

# رتبة السماح بإنشاء/مراجعة التصاريح
ALLOWED_SETUP_ROLE_ID = 1532414187685413055

# الرتبة التي يتم إزالتها عند قبول الطلب
ROLE_TO_REMOVE_ID = 1532414262343897319

# =========================================================
# Settings
# =========================================================

GROQ_MODEL = "llama-3.3-70b-versatile"
DM_TIMEOUT_SECONDS = 300


# =========================================================
# Questions
# =========================================================

QUESTIONS = [
    (
        "name",
        "1️⃣ الاسم الكريم :",
        "لو سمحت أعطيني اسمك الحقيقي:"
    ),
    (
        "age",
        "2️⃣ عمرك الحقيقي :",
        "لو سمحت أعطيني عمرك الحقيقي بالأرقام فقط:"
    ),
    (
        "roblox_main",
        "3️⃣ اسم حسابك الأساسي في روبلوكس :",
        "لو سمحت أعطيني اسم حسابك الأساسي في روبلوكس:"
    ),
    (
        "roblox_short",
        "4️⃣ اختصار حسابك في روبلوكس :",
        "لو سمحت أعطيني الـ Display Name أو اختصار حسابك:"
    ),
    (
        "pledge",
        "5️⃣ قسم الالتزام بقوانين السيرفر :",
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

    role = member.guild.get_role(
        ALLOWED_SETUP_ROLE_ID
    )

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

    channel = bot.get_channel(
        APPLICATION_LOG_CHANNEL_ID
    )

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

    try:

        await channel.send(
            embed=embed
        )

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

        return (
            False,
            "اسم Roblox فارغ."
        )

    url = (
        "https://users.roblox.com/v1/usernames/users"
    )

    payload = {
        "usernames": [username],
        "excludeBannedUsers": False
    }

    try:

        timeout = aiohttp.ClientTimeout(
            total=10
        )

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

                users = data.get(
                    "data",
                    []
                )

                if not users:

                    return (
                        False,
                        "حساب Roblox غير موجود."
                    )

                roblox_name = users[0].get(
                    "name"
                )

                if not roblox_name:

                    return (
                        False,
                        "تعذر الحصول على اسم حساب Roblox."
                    )

                return (
                    True,
                    roblox_name
                )

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
# AI Evaluation
# =========================================================

async def evaluate_application_ai(
    answers: dict
) -> dict:

    api_key = os.getenv(
        "GROQ_API_KEY"
    )

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

التعهد:
{answers.get("pledge")}

الصيغة:

{{
    "decision": "accept",
    "reason": "سبب مختصر بالعربي"
}}
"""

    try:

        client = AsyncGroq(
            api_key=api_key
        )

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

        data = json.loads(
            text
        )

        if data.get("decision") not in {
            "accept",
            "reject",
            "manual_review"
        }:

            raise ValueError(
                "Invalid AI decision"
            )

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

class RPReviewButtons(
    discord.ui.View
):

    def __init__(
        self,
        applicant_id: int,
        roblox_name: str,
        cog: "ApplyCog"
    ):

        super().__init__(
            timeout=None
        )

        self.applicant_id = applicant_id
        self.roblox_name = roblox_name
        self.cog = cog

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

        if not await self._allowed(
            interaction
        ):
            return

        for child in self.children:
            child.disabled = True

        button.label = "✅ تم القبول"

        await interaction.response.edit_message(
            view=self
        )

        await self.cog.finalize_application(
            self.applicant_id,
            self.roblox_name,
            True,
            interaction.user.display_name,
            "قرار يدوي من الإدارة"
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

        if not await self._allowed(
            interaction
        ):
            return

        for child in self.children:
            child.disabled = True

        button.label = "❌ تم الرفض"

        await interaction.response.edit_message(
            view=self
        )

        await self.cog.finalize_application(
            self.applicant_id,
            self.roblox_name,
            False,
            interaction.user.display_name,
            "قرار يدوي من الإدارة"
        )


# =========================================================
# Start Application View
# =========================================================

class ApplyStartView(
    discord.ui.View
):

    def __init__(
        self,
        cog: "ApplyCog"
    ):

        super().__init__(
            timeout=None
        )

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

        self.cog.pending_applicants.add(
            user_id
        )

        try:

            # الرد على الزر أولاً حتى لا يظهر
            # Didn't respond in time
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

class ApplyCog(
    commands.Cog
):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

        self.pending_applicants: set[int] = set()

    async def cog_load(
        self
    ):

        # Persistent panel button
        self.bot.add_view(
            ApplyStartView(self)
        )

        # Persistent review buttons
        self.bot.add_view(
            RPReviewButtons(
                0,
                "",
                self
            )
        )

    # =====================================================
    # Interview
    # =====================================================

    async def run_dm_interview(
        self,
        user: discord.User
    ):

        answers = {}

        def check(
            message: discord.Message
        ):

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

                message = await self.bot.wait_for(
                    "message",
                    check=check,
                    timeout=DM_TIMEOUT_SECONDS
                )

                answer = message.content.strip()

                # =========================================
                # AGE
                # =========================================

                if key == "age":

                    if not answer.isdigit():

                        await user.send(
                            "❌ لو سمحت أدخل عمرك بالأرقام فقط.\n"
                            "مثال: `14`"
                        )

                        return

                    age = int(
                        answer
                    )

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
                reason
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
            name="1️⃣ الاسم الكريم :",
            value=answers.get(
                "name",
                "-"
            ),
            inline=False
        )

        embed.add_field(
            name="2️⃣ العمر :",
            value=answers.get(
                "age",
                "-"
            ),
            inline=True
        )

        embed.add_field(
            name="3️⃣ حساب Roblox :",
            value=(
                f"`{answers.get('roblox_main', '-')}`"
            ),
            inline=True
        )

        embed.add_field(
            name="4️⃣ اختصار Roblox :",
            value=(
                f"`{answers.get('roblox_short', '-')}`"
            ),
            inline=True
        )

        embed.add_field(
    name="5️⃣ التعهد :",
    value=answers.get(
        "pledge",
        "-"
    ),
    inline=False
        )

async def setup(bot):
    await bot.add_cog(ApplyCog(bot))
