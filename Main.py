import discord
from discord.ext import commands, tasks
import asyncio
from groq import AsyncGroq
import json
import os
import random
import logging
import traceback
import aiohttp
import re
from datetime import datetime, timedelta
from keep_alive import keep_alive

# ================= الإعدادات والمتغيرات =================
# قراءة التوكن بأي اسم كان في البيئة تجنباً للمشاكل
TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("DISCORD_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

GUILD_ID = 1532390688187220159
APPLY_CHANNEL_ID = 1532414385794973756
LOG_CHANNEL_ID = 1532414637373657169
STAFF_ROLE_ID = 1524373417137016833
ACCEPTED_ROLE_ID = 1532414257772101812
UNACCEPTED_ROLE_ID = 1532414262343897319 
OVERDUE_ROLE_ID = 1533068412547497984

# رتبة المسؤول المصرح له بضغط زر التسديد
PAYMENT_OFFICER_ROLE_ID = 1532414219843276820

# 🆔 آيدي الروم المخصصة لأمر المخالفات والتصاريح:
TICKET_ALLOWED_CHANNEL_ID = 1532414607577055465

USERS_FILE = os.path.join(os.path.dirname(__file__), "users.json")
# ================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("bot")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# تهيئة عميل Groq للذكاء الاصطناعي
groq_client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

active_applicants: set[int] = set()

OATH_TEXT = (
    "اقسم بالله العظيم انا (اسمك) أن التزم بجميع قوانين السيرفر و أن لا اخرب أثناء الرول بلاي "
    "و أن احترم الاعضاء جميعا و أن احترم جميع أعضاء الإدارة"
)

QUESTIONS = [
    "ما هو اسمك الحقيقي؟",
    "اسمك روبلوكس (الأساسي)؟",
    "كم عمرك؟",
    "📸 يرجى إرسال لقطة شاشة (صورة) لحسابك في روبلوكس يظهر فيها اسم الحساب بوضوح:",
    "سؤال عن المخالفات المرورية:\nكم تبلغ قيمة مخالفة (قطع الإشارة) المعتمدة في السيرفر؟\nأ) 500 داركي\nب) 3000 داركي\nج) 1000 داركي",
    f"اكتب القسم التالي بالكامل واستبدل (اسمك) باسمك الحقيقي، ثم أرسله كرسالة:\n\n\"{OATH_TEXT}\""
]

SYSTEM_PROMPT = """أنت مسؤول مراجعة وتدقيق نصوص طلبات الانضمام لسيرفر رول بلاي روبلوكس.
يجب عليك قبول الطلب تلقائياً طالما أن البيانات المدخلة منطقية:
1. العمر: يجب أن يكون رقماً مقبولاً (مثلاً بين 8 و 99).
2. سؤال المخالفات المرورية: الإجابة الصحيحة لقيمة مخالفة (قطع الإشارة) هي "3000 داركي" أو خيار "ب". أي إجابة تدل على معرفة المبلغ الصحيح (3000) تعتبر مقبولة وصحيحة.
3. القسم: يجب أن يكون المتقدم قد كتب نص القسم بشكل سليم وقام باستبدال كلمة (اسمك) باسمه الحقيقي أو كتب اسمه بدلاً عنها.

ردك يجب أن يكون كود JSON فقط دون أي مقدمات أو مؤخرات كالتالي تماماً:
{"decision": "accept", "reason": "تم قبول طلبك بنجاح والبيانات صحيحة"}
أو إذا كانت الأجوبة فارغة أو مسيئة أو الإجابة على سؤال المخالفات خاطئة أو القسم خاطئ تماماً:
{"decision": "reject", "reason": "اكتب هنا سبب الرفض الواضح بالعربية"}"""


def load_users() -> dict:
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception: pass
    return {}

def save_users(data: dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generate_unique_id() -> str:
    users = load_users()
    existing = {v.get("rp_id") for v in users.values() if isinstance(v, dict)}
    while True:
        new_id = str(random.randint(1000, 999999))
        if new_id not in existing:
            return new_id


async def check_roblox_username(username: str) -> tuple[bool, str]:
    url = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [username.strip()], "excludeBannedUsers": False}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("data", [])
                    if results:
                        return True, results[0].get("name", username)
                    return False, username
    except Exception: pass
    return False, username


async def evaluate_with_ai(real_name: str, primary: str, age: str, traffic_quiz: str, oath: str) -> dict:
    if not groq_client:
        return {"decision": "accept", "reason": "تم القبول التلقائي"}

    text_content = (
        f"الاسم الحقيقي للمتقدم: {real_name}\n"
        f"حساب روبلوكس الأساسي: {primary}\n"
        f"العمر المدخل: {age}\n"
        f"إجابة سؤال المخالفات المرورية (قطع الإشارة): {traffic_quiz}\n"
        f"القسم الذي حلفه المتقدم: {oath}\n"
        f"القسم الأصلي المطلوب للمطابقة: {OATH_TEXT}"
    )
        
    try:
        response = await groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            max_tokens=150,
            temperature=0.1,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text_content}]
        )
        
        raw_text = response.choices[0].message.content.strip()
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(raw_text)
    except Exception as e:
        logger.error(f"خطأ في مراجعة الـ AI: {e}")
        return {"decision": "accept", "reason": "تم القبول التلقائي لسلامة النصوص المكتوبة"}


async def execute_acceptance(guild: discord.Guild, user_id: int, real_name: str, primary_name: str) -> str:
    rp_id = generate_unique_id()
    member = guild.get_member(user_id)
    
    role = guild.get_role(ACCEPTED_ROLE_ID)
    if role and member:
        try: await member.add_roles(role)
        except: pass

    unaccepted_role = guild.get_role(UNACCEPTED_ROLE_ID)
    if unaccepted_role and member:
        try: await member.remove_roles(unaccepted_role)
        except: pass

    # التسمية الجديدة المعتمدة DR
    if member:
        try: await member.edit(nick=f"DR | {primary_name} | {rp_id}")
        except: pass

    users = load_users()
    users[str(user_id)] = {
        "discord_tag": str(member) if member else f"User_{user_id}",
        "real_name": real_name,
        "roblox_primary": primary_name,
        "rp_id": rp_id,
        "tickets": [],
        "permits": []
    }
    save_users(users)
    return rp_id


class ApplyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="تقديم طلب", style=discord.ButtonStyle.blurple, emoji="📝", custom_id="apply_button")
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id in active_applicants:
            return await interaction.response.send_message("⚠️ عندك تقديم شغال حالياً بالخاص.", ephemeral=True)

        active_applicants.add(user_id)
        try:
            dm = await interaction.user.create_dm()
            welcome = discord.Embed(
                title="👋 مرحباً بك في التقديم!",
                description="الرجاء الإجابة على الأسئلة التالية لتتم مراجعة طلبك.\n\n"
                            "⚠️ **شروط التقديم:**\n"
                            "• كل سؤال يجب الرد عليه برسالة منفصلة.\n"
                            "• السؤال الرابع يتطلب رفع صورة لحسابك.\n"
                            "• عندك **5 دقائق** للرد على كل سؤال قبل إلغاء الطلب.",
                color=0x3498db
            )
            await dm.send(embed=welcome)
            
            await interaction.response.send_message(
                embed=discord.Embed(title="بدء التقديم", description="تم إرسال الأسئلة لرسائلك الخاصة!", color=0x2ecc71),
                view=discord.ui.View().add_item(discord.ui.Button(label="الانتقال للخاص", url="https://discord.com/channels/@me", style=discord.ButtonStyle.link)),
                ephemeral=True
            )
            asyncio.create_task(self._collect_answers(interaction, dm))
        except discord.Forbidden:
            active_applicants.discard(user_id)
            await interaction.response.send_message("❌ رسائلك الخاصة مغلقة.", ephemeral=True)


    async def _collect_answers(self, interaction: discord.Interaction, dm: discord.DMChannel):
        answers = []
        image_url = None
        def check(m): return m.author.id == interaction.user.id and isinstance(m.channel, discord.DMChannel)

        try:
            for idx, q in enumerate(QUESTIONS, start=1):
                await dm.send(embed=discord.Embed(title=f"❓ السؤال {idx} من أصل {len(QUESTIONS)}", description=f"**{q}**", color=0x3498db))
                try:
                    msg = await bot.wait_for("message", check=check, timeout=300)
                    if idx == 4:
                        if msg.attachments:
                            image_url = msg.attachments[0].url
                            answers.append("[تم إرفاق الصورة]")
                        else:
                            await dm.send("❌ تم إلغاء الطلب لعدم إرفاق صورة صحيحة.")
                            return
                    else:
                        answers.append(msg.content.strip())
                except asyncio.TimeoutError:
                    await dm.send("⏳ انتهى الوقت وعُلّق الطلب.")
                    return

            await dm.send(embed=discord.Embed(title="🔍 جاري المعالجة والمطابقة...", description="يتم الآن معالجة بياناتك، انتظر ثوانٍ...", color=discord.Color.orange()))
            
            primary_ok, primary_name = await check_roblox_username(answers[1])

            if not primary_ok:
                await dm.send(f"❌ لم نتمكن من إيجاد حساب روبلوكس باسم **{answers[1]}**.")
                await _send_log_async(interaction, answers, "reject", f"الحساب '{answers[1]}' غير موجود في روبلوكس", answers[0], primary_name, None, image_url)
                return

            result = await evaluate_with_ai(
                real_name=answers[0],
                primary=primary_name,
                age=answers[2],
                traffic_quiz=answers[4],
                oath=answers[5]
            )
            
            decision = result.get("decision", "accept")
            reason = result.get("reason", "تم القبول التلقائي")

            rp_id = None
            if decision == "accept":
                rp_id = await execute_acceptance(interaction.guild, interaction.user.id, answers[0], primary_name)
                await dm.send(embed=discord.Embed(title="🎉 تم قبولك!", description=f"🆔 هوية الرول بلاي الخاصة بك: `{rp_id}`", color=discord.Color.green()))
            else:
                await dm.send(embed=discord.Embed(title="❌ نعتذر، تم رفض طلبك تلقائياً", description=f"**السبب:** {reason}\nالإدارة تراجع طلبك الآن وقد يتم قبولك يدوياً.", color=discord.Color.red()))

            await _send_log_async(interaction, answers, decision, reason, answers[0], primary_name, rp_id, image_url)

        except Exception as e: 
            logger.error(f"خطأ أثناء المعالجة: {e}")
        finally: active_applicants.discard(interaction.user.id)


async def _send_log_async(interaction, answers, decision, reason, real_name, primary, rp_id, image_url):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if not log_channel: return

    color = discord.Color.green() if decision == "accept" else discord.Color.red()
    embed = discord.Embed(title="📋 طلب رول بلاي جديد", color=color)
    embed.add_field(name="العضو", value=interaction.user.mention, inline=False)
    embed.add_field(name="الاسم الحقيقي", value=f"`{real_name}`", inline=True)
    embed.add_field(name="حساب روبلوكس", value=f"`{primary}`", inline=True)
    embed.add_field(name="العمر", value=answers[2] if len(answers) > 2 else "غير معروف", inline=True)
    embed.add_field(name="إجابة سؤال المخالفات", value=answers[4] if len(answers) > 4 else "غير متوفر", inline=False)
    embed.add_field(name="قرار البوت الحالي", value="✅ قبول تلقائي" if decision == "accept" else "❌ رفض تلقائي", inline=True)
    embed.add_field(name="السبب", value=reason, inline=True)
    
    if rp_id: embed.add_field(name="🆔 رقم الهوية", value=f"`{rp_id}`", inline=True)
    if image_url: embed.set_image(url=image_url)
    embed.set_footer(text=f"User ID: {interaction.user.id}")

    if decision == "accept":
        view = RevokeView(interaction.user.id)
    else:
        view = StaffOverrideView(interaction.user.id, real_name, primary)

    await log_channel.send(embed=embed, view=view)


class StaffOverrideView(discord.ui.View):
    def __init__(self, applicant_id: int, real_name: str, primary: str):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id
        self.real_name = real_name
        self.primary = primary

    @discord.ui.button(label="قبول يدوياً وتوليد هوية", style=discord.ButtonStyle.success, emoji="🟢")
    async def manual_accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        if staff_role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ ما تملك صلاحية الإدارة.", ephemeral=True)

        await interaction.response.defer()
        rp_id = await execute_acceptance(interaction.guild, self.applicant_id, self.real_name, self.primary)

        member = interaction.guild.get_member(self.applicant_id)
        if member:
            try:
                embed_dm = discord.Embed(title="🎉 تحديث: تم قبولك يدوياً!", description=f"قامت الإدارة بمراجعة طلبك وقبوله يدوياً.\n🆔 **هوية الرول بلاي الخاصة بك:** `{rp_id}`", color=discord.Color.green())
                await member.send(embed=embed_dm)
            except: pass

        for child in self.children: child.disabled = True
        original_embed = interaction.message.embeds[0]
        original_embed.color = discord.Color.green()
        original_embed.add_field(name="تعديل الإدارة", value=f"🟢 تم القبول يدوياً بواسطة {interaction.user.mention}\n🆔 الهوية الممنوحة: `{rp_id}`", inline=False)
        await interaction.message.edit(embed=original_embed, view=self)

    @discord.ui.button(label="إبقاء الرفض", style=discord.ButtonStyle.secondary, emoji="🔒")
    async def keep_reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        if staff_role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ ما تملك صلاحية الإدارة.", ephemeral=True)

        for child in self.children: child.disabled = True
        original_embed = interaction.message.embeds[0]
        original_embed.add_field(name="تعديل الإدارة", value=f"🔒 تم تأكيد الرفض وإغلاق الطلب بواسطة {interaction.user.mention}", inline=False)
        await interaction.message.edit(embed=original_embed, view=self)


class RevokeView(discord.ui.View):
    def __init__(self, applicant_id: int):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id

    @discord.ui.button(label="إزالة القبول (طرد)", style=discord.ButtonStyle.red, emoji="🚫")
    async def revoke(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        if staff_role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("ما تملك صلاحية.", ephemeral=True)

        member = interaction.guild.get_member(self.applicant_id)
        role = interaction.guild.get_role(ACCEPTED_ROLE_ID)
        if member and role and role in member.roles:
            await member.remove_roles(role)
            try: await member.send("⚠️ تم سحب رتبة الرول بلاي منك بواسطة الإدارة.")
            except: pass

        users = load_users()
        if str(self.applicant_id) in users:
            del users[str(self.applicant_id)]
            save_users(users)

        button.disabled = True
        button.label = "تم السحب"
        await interaction.message.edit(view=self)


# ==================== زر تسديد المخالفة ====================
class PayFineButton(discord.ui.View):
    def __init__(self, target_user_id: int, ticket_index: int):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id
        self.ticket_index = ticket_index

    @discord.ui.button(label="💳 تم تسديد المخالفة", style=discord.ButtonStyle.success, custom_id="pay_fine_btn")
    async def pay_fine(self, interaction: discord.Interaction, button: discord.ui.Button):
        officer_role = interaction.guild.get_role(PAYMENT_OFFICER_ROLE_ID)
        if officer_role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ هذا الزر مخصص للضباط المصرح لهم بتأكيد التسديد فقط!", ephemeral=True)

        users = load_users()
        user_key = str(self.target_user_id)

        if user_key not in users or "tickets" not in users[user_key]:
            return await interaction.response.send_message("❌ لم يتم العثور على سجل المخالفة هذا!", ephemeral=True)

        tickets = users[user_key]["tickets"]
        if self.ticket_index >= len(tickets):
            return await interaction.response.send_message("❌ المخالفة مسددة أو غير موجودة!", ephemeral=True)

        tickets[self.ticket_index]["paid"] = True
        save_users(users)

        button.disabled = True
        button.label = f"✅ تم التسديد بواسطة {interaction.user.display_name}"
        button.style = discord.ButtonStyle.secondary
        await interaction.message.edit(view=self)

        await interaction.response.send_message(f"✅ تم تأكيد تسديد المخالفة للمواطن <@{self.target_user_id}> بنجاح بواسطة {interaction.user.mention}.")

        # إزالة إيقاف الخدمات إذا سدد كل مخالفاته
        member = interaction.guild.get_member(self.target_user_id)
        if member:
            has_unpaid = any(not t.get("paid", False) for t in tickets)
            if not has_unpaid:
                overdue_role = interaction.guild.get_role(OVERDUE_ROLE_ID)
                if overdue_role and overdue_role in member.roles:
                    try:
                        await member.remove_roles(overdue_role)
                        await interaction.channel.send(f"🟢 **تحديث:** تم رفع إيقاف الخدمات عن المواطن {member.mention} لعدم وجود مخالفات قائمة.")
                    except: pass


# ==================== نظام المخالفات المرورية ====================
class FineSelect(discord.ui.Select):
    def __init__(self, target_member: discord.Member, rp_id: str, proof_url: str):
        self.target_member = target_member
        self.rp_id = rp_id
        self.proof_url = proof_url

        options = [
            discord.SelectOption(label="سرعة زائدة", description="الغرامة: 500 داركي", value="500|سرعة زائدة"),
            discord.SelectOption(label="قطع الإشارة", description="الغرامة: 3000 داركي", value="3000|قطع الإشارة"),
            discord.SelectOption(label="إزالة لوحة (حجز)", description="الغرامة: 2000 داركي", value="2000|إزالة لوحة (حجز)"),
            discord.SelectOption(label="عدم إضاءة النور أثناء الليل", description="الغرامة: 300 داركي", value="300|عدم إضاءة النور أثناء الليل"),
            discord.SelectOption(label="عدم الالتزام بالمسار", description="الغرامة: 400 داركي", value="400|عدم الالتزام بالمسار"),
            discord.SelectOption(label="إزعاج بدون سبب (حجز)", description="الغرامة: 700 داركي", value="700|إزعاج بدون سبب (حجز)"),
            discord.SelectOption(label="وقوف وسط الطريق (حجز)", description="الغرامة: 1000 داركي", value="1000|وقوف وسط الطريق (حجز)"),
            discord.SelectOption(label="عدم إفساح الطريق لمركبات الطوارئ", description="الغرامة: 200 داركي", value="200|عدم إفساح الطريق لمركبات الطوارئ"),
            discord.SelectOption(label="تعديل بدون تصريح (حجز/حرمان)",
