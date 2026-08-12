import asyncio
import json
import os
import random
import logging

import aiohttp
import discord
from discord.ext import commands


logger = logging.getLogger("bot")


# =========================================================
# IDs
# =========================================================

REVIEW_CHANNEL_ID = 1532414607577055465

# رتبة القبول
PASSED_ROLE_ID = 1532414257772101812

# رتبة السماح بالمراجعة / setup
ALLOWED_SETUP_ROLE_ID = 1532414187685413055

# الرتبة التي يتم إزالتها عند قبول العضو
ROLE_TO_REMOVE_ID = 1532414262343897319

# قناة اللوقز
LOG_CHANNEL_ID = 1532414607577055465


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
        "انسخ القسم التالي وعبّي اسمك مكان ( اسمك ) وأرسله كما هو:\n\n"
        "** اقسم بالله العظيم انا ( اسمك ) احترم قوانين سيرفر دارك سيتي واعضائه "
        "وما اخرب او اسب وانا على حلفي ووعدي **"
    ),
]


# =========================================================
# Permissions
# =========================================================

def has_review_permission(member: discord.Member) -> bool:
    """Check whether a member is allowed to accept/reject applications."""

    if member.guild_permissions.administrator:
        return True

    role = member.guild.get_role(ALLOWED_SETUP_ROLE_ID)

    return role is not None and role in member.roles


# =========================================================
# Logs
# =========================================================

async def get_log_channel(bot: commands.Bot):
    if not LOG_CHANNEL_ID:
        return None

    channel = bot.get_channel(LOG_CHANNEL_ID)

    if channel is None:
        try:
            channel = await bot.fetch_channel(LOG_CHANNEL_ID)
        except Exception:
            logger.warning(
                "Log channel %s not found/accessible",
                LOG_CHANNEL_ID
            )
            return None

    return channel


async def send_log(bot: commands.Bot, embed: discord.Embed):
    channel = await get_log_channel(bot)

    if channel:
        try:
            await channel.send(embed=embed)

        except Exception as e:
            logger.warning(
                "Failed to send log: %s",
                e
            )

    else:
        logger.info(
            "[LOG] %s",
            embed.title
        )


# =========================================================
# Roblox API
# =========================================================

async def check_roblox_username(username: str) -> tuple[bool, str]:
    """
    يتحقق من وجود حساب Roblox باستخدام Roblox Users API الرسمي.

    يرجع:
    (True, اسم الحساب الرسمي)
    أو
    (False, سبب الخطأ)
    """

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

                    logger.warning(
                        "Roblox API returned status %s",
                        response.status
                    )

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

                roblox_user = users[0]

                verified_username = roblox_user.get(
                    "name"
                )

                if not verified_username:
                    return (
                        False,
                        "تعذر الحصول على اسم حساب Roblox."
                    )

                return (
                    True,
                    verified_username
                )

    except asyncio.TimeoutError:

        return (
            False,
            "انتهى وقت الاتصال بخدمة Roblox."
        )

    except aiohttp.ClientError as e:

        logger.warning(
            "Roblox API connection error: %s",
            e
        )

        return (
            False,
            "حدث خطأ أثناء الاتصال بخدمة Roblox."
        )

    except Exception as e:

        logger.exception(
            "Unexpected Roblox API error: %s",
            e
        )

        return (
            False,
            "حدث خطأ غير متوقع أثناء التحقق من حساب Roblox."
        )


# =========================================================
# Groq AI
# =========================================================

async def evaluate_application_ai(answers: dict) -> dict:
    """
    يرسل الإجابات لنموذج Groq لتحليل الطلب.

    العمر يتم التحقق منه برمجياً قبل الوصول هنا،
    لذلك الذكاء الاصطناعي لا يقرر إذا كان العمر أقل أو أكبر.
    """

    api_key = os.getenv(
        "GROQ_API_KEY"
    )

    if not api_key:

        logger.warning(
            "GROQ_API_KEY غير موجود"
        )

        return {
            "decision": "manual_review",
            "reason": "مفتاح API غير مضبوط بالسيرفر"
        }

    try:

        from groq import AsyncGroq

    except ImportError:

        logger.error(
            "مكتبة groq غير مثبتة. أضفها إلى requirements.txt"
        )

        return {
            "decision": "manual_review",
            "reason": "مكتبة groq غير مثبتة"
        }

    client = AsyncGroq(
        api_key=api_key
    )

    prompt = f"""
أنت مشرف يراجع طلبات انضمام لسيرفر رول بلاي على ديسكورد.

مهم جداً:
العمر تم التحقق منه برمجياً مسبقاً.
لا تحاول تغيير أو تفسير العمر.

قرر قراراً واحداً فقط:

- "reject": إذا كان هناك كلام غير لائق، إساءة، سبام،
  إجابات فارغة أو عشوائية أو غير منطقية.
- "accept": إذا كانت الإجابات جادة ومنطقية وخالية من المشاكل.
- "manual_review": إذا كان هناك شك حقيقي.

الإجابات:

الاسم:
{answers.get("name")}

العمر:
{answers.get("age")}

حساب Roblox:
{answers.get("roblox_main")}

اختصار Roblox:
{answers.get("roblox_short")}

التعهد:
{answers.get("pledge")}

رد فقط بصيغة JSON:

{{"decision": "accept أو reject أو manual_review", "reason": "سبب مختصر بالعربي"}}
"""

    try:

        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            max_tokens=300,
            temperature=0.2,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
        )

        text = (
            response.choices[0]
            .message.content
            or ""
        ).strip()

        text = (
            text
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        data = json.loads(text)

        if data.get("decision") not in (
            "accept",
            "reject",
            "manual_review"
        ):
            raise ValueError(
                f"decision غير متوقع: {data.get('decision')}"
            )

        return data

    except Exception as e:

        logger.error(
            "فشل تحليل الطلب بالذكاء الاصطناعي: %s",
            e,
            exc_info=True
        )

        return {
            "decision": "manual_review",
            "reason": f"خطأ تقني بالتحليل الآلي: {e}"
        }


# =========================================================
# Review Buttons
# =========================================================

class RPReviewButtons(discord.ui.View):

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

    async def _resolve_and_lock(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ) -> bool:

        if not has_review_permission(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ لا تملك صلاحية القيام بهذا الإجراء.",
                ephemeral=True
            )

            return False

        if button.disabled:

            await interaction.response.send_message(
                "⚠️ تم التعامل مع هذا الطلب بالفعل.",
                ephemeral=True
            )

            return False

        return True

    @discord.ui.button(
        label="✅ قبول الطلب",
        style=discord.ButtonStyle.success,
        custom_id="rp_review_accept"
    )
    async def accept(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not await self._resolve_and_lock(
            interaction,
            button
        ):
            return

        for child in self.children:
            child.disabled = True

        button.label = (
            f"✅ مقبول بواسطة "
            f"{interaction.user.display_name}"
        )

        await interaction.response.edit_message(
            view=self
        )

        await self.cog.finalize_application(
            self.applicant_id,
            self.roblox_name,
            accepted=True,
            decided_by=interaction.user.display_name,
            reason="قرار يدوي من الإدارة"
        )

    @discord.ui.button(
        label="❌ رفض الطلب",
        style=discord.ButtonStyle.danger,
        custom_id="rp_review_reject"
    )
    async def reject(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not await self._resolve_and_lock(
            interaction,
            button
        ):
            return

        for child in self.children:
            child.disabled = True

        button.label = (
            f"❌ مرفوض بواسطة "
            f"{interaction.user.display_name}"
        )

        await interaction.response.edit_message(
            view=self
        )

        await self.cog.finalize_application(
            self.applicant_id,
            self.roblox_name,
            accepted=False,
            decided_by=interaction.user.display_name,
            reason="قرار يدوي من الإدارة"
        )


# =========================================================
# Start Application Button
# =========================================================

class ApplyStartView(discord.ui.View):

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
        custom_id="replit_apply_btn_final"
    )
    async def start_apply(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user.id in self.cog.pending_applicants:

            return await interaction.response.send_message(
                "⏳ عندك طلب قيد التقديم أو المراجعة حالياً، "
                "تفقد الخاص أو انتظر الرد.",
                ephemeral=True
            )

        self.cog.pending_applicants.add(
            interaction.user.id
        )

        try:

            await interaction.user.send(
                "📝 أهلاً بك!\n"
                "رح أرسلك بضع أسئلة، جاوب عليها وحدة وحدة."
            )

        except discord.Forbidden:

            self.cog.pending_applicants.discard(
                interaction.user.id
            )

            return await interaction.response.send_message(
                "❌ ما قدرت أرسلك رسالة خاصة!\n"
                "تأكد إن الخاص مفتوح عندك وحاول مرة ثانية.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "📩 شيك الخاص، أرسلتلك الأسئلة هناك!",
            ephemeral=True
        )

        asyncio.create_task(
            self.cog.run_dm_interview(
                interaction.user
            )
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

    # =====================================================
    # DM Interview
    # =====================================================

    async def run_dm_interview(
        self,
        user: discord.User
    ):

        answers = {}

        def check(
            m: discord.Message
        ):

            return (
                m.author.id == user.id
                and isinstance(
                    m.channel,
                    discord.DMChannel
                )
            )

        try:

            for (
                key,
                title,
                description
            ) in QUESTIONS:

                question_embed = discord.Embed(
                    title=title,
                    description=description,
                    color=discord.Color.blurple()
                )

                question_embed.set_footer(
                    text="إدارة سيرفر دارك سيتي 📗"
                )

                await user.send(
                    embed=question_embed
                )

                msg = await self.bot.wait_for(
                    "message",
                    check=check,
                    timeout=DM_TIMEOUT_SECONDS
                )

                answer = msg.content.strip()

                # =========================================
                # Age Validation
                # =========================================

                if key == "age":

                    if not answer.isdigit():

                        await user.send(
                            "❌ لو سمحت أدخل عمرك بالأرقام فقط.\n"
                            "مثال: `14`"
                        )

                        self.pending_applicants.discard(
                            user.id
                        )

                        return

                    age = int(answer)

                    if age < 10:

                        await user.send(
                            "❌ عذراً، يجب أن يكون عمرك "
                            "10 سنوات أو أكثر للتقديم."
                        )

                        self.pending_applicants.discard(
                            user.id
                        )

                        return

                    if age > 80:

                        await user.send(
                            "❌ الرجاء إدخال عمر صحيح."
                        )

                        self.pending_applicants.discard(
                            user.id
                        )

                        return

                # =========================================
                # Roblox Validation
                # =========================================

                if key == "roblox_main":

                    checking_message = await user.send(
                        "🔎 جاري التحقق من حساب Roblox، "
                        "لو سمحت انتظر..."
                    )

                    exists, result = await check_roblox_username(
                        answer
                    )

                    if not exists:

                        await checking_message.edit(
                            content=(
                                f"❌ لم يتم العثور على حساب Roblox "
                                f"باسم `{answer}`.\n\n"
                                "لو سمحت تأكد من اسم الحساب "
                                "وأرسله مرة ثانية."
                            )
                        )

                        self.pending_applicants.discard(
                            user.id
                        )

                        return

                    answers["roblox_main"] = result

                    await checking_message.edit(
                        content=(
                            f"✅ تم العثور على حساب Roblox: "
                            f"`{result}`"
                        )
                    )

                    continue

                # =========================================
                # Pledge Validation
                # =========================================

                if key == "pledge":

                    required_phrase = (
                        "احترم قوانين سيرفر دارك سيتي"
                    )

                    if required_phrase not in answer:

                        await user.send(
                            "❌ لو سمحت انسخ نص التعهد "
                            "بالشكل المطلوب مع تعبئة اسمك."
                        )

                        self.pending_applicants.discard(
                            user.id
                        )

                        return

                answers[key] = answer

        except asyncio.TimeoutError:

            await user.send(
                "⌛ انتهى الوقت المسموح للرد.\n"
                "الرجاء تقديم الطلب من جديد."
            )

            self.pending_applicants.discard(
                user.id
            )

            return

        except discord.Forbidden:

            self.pending_applicants.discard(
                user.id
            )

            return

        await user.send(
            "✅ تم استلام إجاباتك.\n"
            "جاري تحليل طلبك، رح توصلك النتيجة قريباً."
        )

        logger.info(
            "Collected application answers from %s (%s)",
            user,
            user.id
        )

        # =================================================
        # AI Evaluation
        # =================================================

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

        # =================================================
        # Received Log
        # =================================================

        received_embed = discord.Embed(
            title=(
                "📋 طلب رول بلاي جديد"
                if decision != "manual_review"
                else
                "📋 طلب رول بلاي - يحتاج مراجعة يدوية"
            ),
            color=discord.Color.blue()
        )

        received_embed.add_field(
            name="العضو",
            value=(
                f"{user.mention} "
                f"(`{user.id}`)"
            ),
            inline=False
        )

        received_embed.add_field(
            name="الاسم",
            value=answers.get(
                "name",
                "-"
            ),
         
