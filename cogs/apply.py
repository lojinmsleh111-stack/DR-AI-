import asyncio
import json
import os
import discord
from discord.ext import commands
import logging

logger = logging.getLogger("bot")

REVIEW_CHANNEL_ID = 1532414607577055465
PASSED_ROLE_ID = 1524373417137016833
ALLOWED_SETUP_ROLE_ID = 1532414187685413055

# TODO: ضع هون الـ ID تبع قناة اللوقز الخاصة بالإدارة
LOG_CHANNEL_ID = 1532414607577055465

# الموديل المستخدم لتحليل الطلبات عبر Groq (سريع ومجاني ضمن الحدود المسموحة)
GROQ_MODEL = "llama-3.3-70b-versatile"

DM_TIMEOUT_SECONDS = 300  # 5 دقائق للرد على كل سؤال قبل ما ينتهي الطلب تلقائياً

# ترتيب الأسئلة يلي بترسل بالخاص كـ Embed، وحدة وحدة
# كل عنصر: (المفتاح، عنوان الإيمبد، وصف/نص السؤال)
QUESTIONS = [
    ("name", "1️⃣ الاسم الكريم", "أدخل اسمك..."),
    ("age", "2️⃣ عمرك الحقيقي", "الرجاء وضع عمرك الحقيقي (أرقام فقط)..."),
    ("roblox_main", "3️⃣ اسم حسابك الأساسي في روبلوكس", "Username..."),
    ("roblox_short", "4️⃣ اختصار الحساب", "Display Name / اليوزر..."),
    (
        "pledge",
        "5️⃣ قسم الالتزام بقوانين السيرفر",
        "انسخ القسم التالي وعبّي اسمك مكان ( اسمك ) وأرسله كما هو:\n\n"
        "** اقسم بالله العظيم انا ( اسمك ) احترم قوانين سيرفر دارك سيتي واعضائه "
        "وما اخرب او اسب وانا على حلفي ووعدي **",
    ),
]


def has_review_permission(member: discord.Member) -> bool:
    """Check whether a member is allowed to accept/reject applications."""
    if member.guild_permissions.administrator:
        return True
    role = member.guild.get_role(ALLOWED_SETUP_ROLE_ID)
    return role is not None and role in member.roles


async def get_log_channel(bot: commands.Bot):
    if not LOG_CHANNEL_ID:
        return None
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(LOG_CHANNEL_ID)
        except Exception:
            logger.warning("Log channel %s not found/accessible", LOG_CHANNEL_ID)
            return None
    return channel


async def send_log(bot: commands.Bot, embed: discord.Embed):
    channel = await get_log_channel(bot)
    if channel:
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.warning("Failed to send log: %s", e)
    else:
        logger.info("[LOG] %s", embed.title)


async def evaluate_application_ai(answers: dict) -> dict:
    """
    يرسل الإجابات لنموذج Claude ليحلل الطلب بشكل شامل.
    يرجع dict: {"decision": "accept"|"reject"|"manual_review", "reason": "..."}
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("GROQ_API_KEY غير موجود بمتغيرات البيئة، رح يتم تحويل الطلب للمراجعة اليدوية")
        return {"decision": "manual_review", "reason": "مفتاح API غير مضبوط بالسيرفر"}

    try:
        from groq import AsyncGroq
    except ImportError:
        logger.error("مكتبة groq غير مثبتة. ضيفها لـ requirements.txt: groq")
        return {"decision": "manual_review", "reason": "مكتبة groq غير مثبتة"}

    client = AsyncGroq(api_key=api_key)

    prompt = f"""أنت مشرف يراجع طلبات انضمام لسيرفر رول بلاي على ديسكورد. حلل الإجابات التالية وقرر قرار واحد:

- "reject": إذا في كلام غير لائق، إساءة، سبام، إجابات فارغة/عشوائية/غير منطقية، أو عمر غير معقول (أقل من 10 أو أكبر من 80).
- "accept": إذا كل الإجابات جادة، منطقية، وخالية من أي مشاكل واضحة.
- "manual_review": إذا في شك حقيقي أو حالة حدّية ما تقدر تحسمها بثقة عالية.

الإجابات:
الاسم: {answers.get('name')}
العمر: {answers.get('age')}
حساب روبلوكس الأساسي: {answers.get('roblox_main')}
اختصار الحساب: {answers.get('roblox_short')}
نص التعهد: {answers.get('pledge')}

رد فقط بصيغة JSON صافية بدون أي نص أو markdown إضافي، بهذا الشكل بالضبط:
{{"decision": "accept أو reject أو manual_review", "reason": "سبب مختصر بالعربي بجملة أو جملتين"}}"""

    try:
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            max_tokens=300,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )
        text = (response.choices[0].message.content or "").strip()
        text = text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)
        if data.get("decision") not in ("accept", "reject", "manual_review"):
            raise ValueError(f"decision غير متوقع: {data.get('decision')}")
        return data
    except Exception as e:
        logger.error("فشل تحليل الطلب بالذكاء الاصطناعي: %s", e, exc_info=True)
        return {"decision": "manual_review", "reason": f"خطأ تقني بالتحليل الآلي: {e}"}


class RPReviewButtons(discord.ui.View):
    def __init__(self, applicant_id: int, char_name: str, cog: "ApplyCog"):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id
        self.char_name = char_name
        self.cog = cog

    async def _resolve_and_lock(self, interaction: discord.Interaction, button: discord.ui.Button) -> bool:
        if not has_review_permission(interaction.user):
            await interaction.response.send_message("❌ لا تملك صلاحية القيام بهذا الإجراء.", ephemeral=True)
            return False
        if button.disabled:
            await interaction.response.send_message("⚠️ تم التعامل مع هذا الطلب بالفعل.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ قبول الطلب", style=discord.ButtonStyle.success, custom_id="rp_review_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._resolve_and_lock(interaction, button):
            return
        for child in self.children:
            child.disabled = True
        button.label = f"✅ مقبول بواسطة {interaction.user.display_name}"
        await interaction.response.edit_message(view=self)
        await self.cog.finalize_application(
            self.applicant_id, self.char_name, accepted=True,
            decided_by=interaction.user.display_name, reason="قرار يدوي من الإدارة"
        )

    @discord.ui.button(label="❌ رفض الطلب", style=discord.ButtonStyle.danger, custom_id="rp_review_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._resolve_and_lock(interaction, button):
            return
        for child in self.children:
            child.disabled = True
        button.label = f"❌ مرفوض بواسطة {interaction.user.display_name}"
        await interaction.response.edit_message(view=self)
        await self.cog.finalize_application(
            self.applicant_id, self.char_name, accepted=False,
            decided_by=interaction.user.display_name, reason="قرار يدوي من الإدارة"
        )


class ApplyStartView(discord.ui.View):
    def __init__(self, cog: "ApplyCog"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="تقديم طلب تصريح رول بلاي",
        style=discord.ButtonStyle.blurple,
        emoji="👾",
        custom_id="replit_apply_btn_final"
    )
    async def start_apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.cog.pending_applicants:
            return await interaction.response.send_message(
                "⏳ عندك طلب قيد التقديم أو المراجعة حالياً، تفقد الخاص أو انتظر الرد.", ephemeral=True
            )

        self.cog.pending_applicants.add(interaction.user.id)

        try:
            await interaction.user.send("📝 أهلاً بك! رح أرسلك بضع أسئلة، جاوب عليها وحدة وحدة بنفس هالمحادثة.")
        except discord.Forbidden:
            self.cog.pending_applicants.discard(interaction.user.id)
            return await interaction.response.send_message(
                "❌ ما قدرت أرسلك رسالة خاصة! تأكد إن الخاص مفتوح عندك للأعضاء بهاد السيرفر وحاول مرة ثانية.",
                ephemeral=True
            )

        await interaction.response.send_message("📩 شيك الخاص، أرسلتلك الأسئلة هناك!", ephemeral=True)

        # يشتغل بالخلفية عشان ما يعلّق الـ interaction (فيه انتظار طويل لردود المستخدم)
        asyncio.create_task(self.cog.run_dm_interview(interaction.user))


class ApplyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # يتتبع الأعضاء يلي بمنتصف تعبئة الطلب أو بانتظار مراجعة
        self.pending_applicants: set[int] = set()

    async def cog_load(self):
        self.bot.add_view(ApplyStartView(self))

    async def run_dm_interview(self, user: discord.User):
        answers = {}

        def check(m: discord.Message):
            return m.author.id == user.id and isinstance(m.channel, discord.DMChannel)

        try:
            for key, title, description in QUESTIONS:
                question_embed = discord.Embed(
                    title=title,
                    description=description,
                    color=discord.Color.blurple()
                )
                question_embed.set_footer(text="إدارة سيرفر دارك سيتي 📗")
                await user.send(embed=question_embed)
                msg = await self.bot.wait_for("message", check=check, timeout=DM_TIMEOUT_SECONDS)
                answer = msg.content.strip()

                if key == "age":
                    if not answer.isdigit() or not (1 <= int(answer) <= 120):
                        await user.send("❌ الرجاء إدخال عمر صحيح (أرقام فقط). قدّم الطلب من جديد بالضغط على الزر.")
                        self.pending_applicants.discard(user.id)
                        return

                if key == "pledge":
                    required_phrase = "احترم قوانين سيرفر دارك سيتي"
                    if required_phrase not in answer:
                        await user.send(
                            "❌ الرجاء نسخ نص القسم بالضبط مع تعبئة اسمك مكان ( اسمك ). "
                            "قدّم الطلب من جديد بالضغط على الزر."
                        )
                        self.pending_applicants.discard(user.id)
                        return

                answers[key] = answer

        except asyncio.TimeoutError:
            await user.send("⌛ انتهى الوقت المسموح للرد، الرجاء تقديم الطلب من جديد.")
            self.pending_applicants.discard(user.id)
            return
        except discord.Forbidden:
            self.pending_applicants.discard(user.id)
            return

        await user.send("✅ تم استلام إجاباتك، جاري تحليل طلبك، رح توصلك النتيجة قريباً.")
        logger.info("Collected application answers from %s (%s)", user, user.id)

        ai_result = await evaluate_application_ai(answers)
        decision = ai_result.get("decision", "manual_review")
        reason = ai_result.get("reason", "")

        received_embed = discord.Embed(
            title="📋 طلب رول بلاي جديد" if decision != "manual_review" else "📋 طلب رول بلاي - يحتاج مراجعة يدوية",
            color=discord.Color.blue()
        )
        received_embed.add_field(name="العضو", value=f"{user.mention} (`{user.id}`)", inline=False)
        received_embed.add_field(name="الاسم", value=answers.get("name", "-"), inline=True)
        received_embed.add_field(name="العمر", value=answers.get("age", "-"), inline=True)
        received_embed.add_field(name="قرار الذكاء الاصطناعي", value=decision, inline=True)
        received_embed.add_field(name="السبب", value=reason or "-", inline=False)
        await send_log(self.bot, received_embed)

        if decision in ("accept", "reject"):
            await self.finalize_application(
                user.id, answers.get("name", user.display_name),
                accepted=(decision == "accept"),
                decided_by="🤖 الذكاء الاصطناعي",
                reason=reason,
            )
        else:
            await self.send_for_manual_review(user, answers)

    async def send_for_manual_review(self, user: discord.User, answers: dict):
        review_channel = self.bot.get_channel(REVIEW_CHANNEL_ID)
        if review_channel is None:
            try:
                review_channel = await self.bot.fetch_channel(REVIEW_CHANNEL_ID)
            except Exception:
                logger.warning("Review channel %s not found/accessible", REVIEW_CHANNEL_ID)
                return

        embed = discord.Embed(
            title="📑 طلب تصريح رول بلاي (مراجعة يدوية)",
            description=f"قدم المواطن {user.mention} طلب للحصول على التصريح.",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="👤 العضو", value=f"{user.mention} (`{user.id}`)", inline=False)
        embed.add_field(name="1️⃣ الاسم الكريم:", value=answers.get("name", "-"), inline=False)
        embed.add_field(name="2️⃣ عمرك الحقيقي:", value=answers.get("age", "-"), inline=True)
        embed.add_field(name="3️⃣ اسم حسابك الأساسي:", value=f"`{answers.get('roblox_main', '-')}`", inline=True)
        embed.add_field(name="4️⃣ اختصار الحساب:", value=f"`{answers.get('roblox_short', '-')}`", inline=True)
        embed.add_field(name="5️⃣ التعهد:", value=answers.get("pledge", "-"), inline=False)

        view = RPReviewButtons(applicant_id=user.id, char_name=answers.get("name", user.display_name), cog=self)
        await review_channel.send(embed=embed, view=view)

    async def finalize_application(self, applicant_id: int, char_name: str, accepted: bool, decided_by: str, reason: str = ""):
        guild = None
        for g in self.bot.guilds:
            if g.get_member(applicant_id):
                guild = g
                break

        member = guild.get_member(applicant_id) if guild else None

        if accepted:
            role = guild.get_role(PASSED_ROLE_ID) if guild else None
            if member:
                if role:
                    try:
                        await member.add_roles(role)
                    except Exception as e:
                        logger.warning("Failed to add role to %s: %s", applicant_id, e)
                try:
                    await member.edit(nick=char_name)
                except Exception as e:
                    logger.warning("Failed to set nickname for %s: %s", applicant_id, e)
                try:
                    text = "🎉 **مبروك!** تم قبول طلب تصريح الرول بلاي الخاص بك بنجاح."
                    if reason:
                        text += f"\nملاحظة: {reason}"
                    await member.send(text)
                except Exception:
                    pass
            logger.info("Application %s accepted by %s", applicant_id, decided_by)
        else:
            if member:
                try:
                    text = "❌ نأسف لإبلاغك بأنه تم رفض طلب تصريح الرول بلاي الخاص بك."
                    if reason:
                        text += f"\nالسبب: {reason}"
                    await member.send(text)
                except Exception:
                    pass
            logger.info("Application %s rejected by %s", applicant_id, decided_by)

        decision_embed = discord.Embed(
            title="✅ تم قبول الطلب" if accepted else "❌ تم رفض الطلب",
            color=discord.Color.green() if accepted else discord.Color.red()
        )
        decision_embed.add_field(name="العضو", value=f"<@{applicant_id}> (`{applicant_id}`)", inline=False)
        decision_embed.add_field(name="بواسطة", value=decided_by, inline=True)
        if reason:
            decision_embed.add_field(name="السبب", value=reason, inline=False)
        await send_log(self.bot, decision_embed)

        self.pending_applicants.discard(applicant_id)

    @commands.command(name="setup_apply")
    async def setup_apply(self, ctx):
        if not has_review_permission(ctx.author):
            return await ctx.send("❌ عفواً، هذا الأمر مخصص لرتبة معينة فقط!")

        embed = discord.Embed(
            title="🎮 طلب تصريح دخول الرول بلاي",
            description="أهلاً بك في السيرفر!\n\nللحصول على تصريح الرول بلاي، اضغط على الزر بالأسفل. رح نرسلك الأسئلة بالخاص.",
            color=discord.Color.blurple()
        )
        embed.set_footer(text="إدارة سيرفر دارك سيتي 📗")

        await ctx.send(embed=embed, view=ApplyStartView(self))
        try:
            await ctx.message.delete()
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(ApplyCog(bot))
        
