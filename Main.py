import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import random
import logging
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# ==================== إعدادات التسجيل ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_bot")

# ==================== الإعدادات والثوابت ====================
TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_BOT_TOKEN_HERE")
GUILD_ID = 1532413725515321354  # آيدي السيرفر

# معرفات الرتب
STAFF_ROLE_ID = 1532414219843276820        # رتبة العسكري / الإدارة المسموح لهم بإدارة المخالفات
PAYMENT_OFFICER_ROLE_ID = 1532414219843276820 # الرتبة المسموح لها بتأكيد تسديد المخالفات
ACCEPTED_ROLE_ID = 1532414282367762604     # رتبة المقبولين
UNACCEPTED_ROLE_ID = 1532414332401877074   # رتبة غير المقبولين
OVERDUE_ROLE_ID = 1532414352220098670      # رتبة إيقاف الخدمات

# معرفات الرومات
APPLY_CHANNEL_ID = 1532414578502148157          # روم التقديم
LOG_CHANNEL_ID = 1532414637373657169            # روم السجلات (اللوق)
TICKET_ALLOWED_CHANNEL_ID = 1532414607577055465  # روم المخالفات والتصاريح

# ملف إعدادات البيانات
DATA_FILE = "users_data.json"

# ==================== إعداد البوت ====================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ==================== خادم Flask لإبقاء البوت نشطاً ====================
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    # Render يحدد المنفذ تلقائياً عبر البيئة
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
    

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# ==================== التعامل مع قواعد البيانات ====================
def load_users():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"خطأ أثناء تحميل البيانات: {e}")
        return {}

def save_users(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"خطأ أثناء حفظ البيانات: {e}")

def generate_unique_id():
    users = load_users()
    existing_ids = {u.get("rp_id") for u in users.values() if "rp_id" in u}
    while True:
        new_id = str(random.randint(100000, 999999))
        if new_id not in existing_ids:
            return new_id

# ==================== نظام القبول التلقائي وتغيير الاسم ====================
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

    # تغيير الاسم لتبدأ بـ DR بدلاً من RC
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

# ==================== نموذج التقديم (Modal) ====================
class ApplyModal(discord.ui.Modal, title="📝 نموذج التقديم للرول بلاي"):
    real_name = discord.ui.TextInput(label="الاسم الحقيقي", placeholder="أدخل اسمك الحقيقي...", required=True)
    roblox_primary = discord.ui.TextInput(label="اسم حساب روبلوكس الرئيسي", placeholder="Primary Roblox Username...", required=True)
    roblox_alt = discord.ui.TextInput(label="اسم حساب روبلوكس الاحتياطي (إن وجد)", placeholder="Alt Roblox Username...", required=False)
    age = discord.ui.TextInput(label="العمر", placeholder="أدخل عمرك...", required=True, max_length=3)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user = interaction.user

        rp_id = await execute_acceptance(guild, user.id, self.real_name.value, self.roblox_primary.value)

        embed_log = discord.Embed(
            title="📥 طلب تقديم جديد (تم القبول تلقائياً)",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed_log.add_field(name="العضو", value=user.mention, inline=True)
        embed_log.add_field(name="الاسم الحقيقي", value=self.real_name.value, inline=True)
        embed_log.add_field(name="رقم الهوية (RP ID)", value=f"`{rp_id}`", inline=True)
        embed_log.add_field(name="حساب روبلوكس الرئيسي", value=self.roblox_primary.value, inline=False)
        embed_log.add_field(name="حساب روبلوكس الاحتياطي", value=self.roblox_alt.value or "لا يوجد", inline=False)
        embed_log.add_field(name="العمر", value=self.age.value, inline=True)
        embed_log.set_thumbnail(url=user.display_avatar.url)

        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(embed=embed_log)

        try:
            embed_dm = discord.Embed(
                title="🎉 تهانينا! تم قبولك في الرول بلاي",
                description=f"مرحباً بك **{self.real_name.value}**، تم قبول تقديمك بنجاح وحصولك على رتبة التفعيل.\n\n"
                            f"🆔 **رقم الهوية الخاص بك:** `{rp_id}`\n"
                            f"🏷️ **اسمك في السيرفر:** `DR | {self.roblox_primary.value} | {rp_id}`",
                color=discord.Color.blue()
            )
            await user.send(embed=embed_dm)
        except: pass

        await interaction.followup.send("✅ تم تسجيل تقديمك وقبولك بنجاح! تم تحديث رتبك واسمك.", ephemeral=True)

class ApplyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📝 تقديم طلب التفعيل", style=discord.ButtonStyle.primary, custom_id="apply_button_pers")
    async def apply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ApplyModal())

# ==================== زر تسديد المخالفة ====================
class PayFineButton(discord.ui.View):
    def __init__(self, target_user_id: int, ticket_index: int):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id
        self.ticket_index = ticket_index

    @discord.ui.button(label="💳 تم تسديد المخالفة", style=discord.ButtonStyle.success, custom_id="pay_fine_btn")
    async def pay_fine(self, interaction: discord.Interaction, button: discord.ui.Button):
        # التحقق من امتلاك الرتبة المحددة
        officer_role = interaction.guild.get_role(PAYMENT_OFFICER_ROLE_ID)
        if officer_role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ عفواً، هذا الزر مخصص للمسؤولين المصرح لهم بتأكيد التسديد فقط!", ephemeral=True)

        users = load_users()
        user_key = str(self.target_user_id)

        if user_key not in users or "tickets" not in users[user_key]:
            return await interaction.response.send_message("❌ لم يتم العثور على سجل المخالفة هذا!", ephemeral=True)

        tickets = users[user_key]["tickets"]
        if self.ticket_index >= len(tickets):
            return await interaction.response.send_message("❌ المخالفة غير موجودة أو تم تسديدها سابقاً!", ephemeral=True)

        # تحديث حالة السداد
        tickets[self.ticket_index]["paid"] = True
        save_users(users)

        # تعطيل الزر
        button.disabled = True
        button.label = f"✅ تم التسديد بواسطة {interaction.user.display_name}"
        button.style = discord.ButtonStyle.secondary
        await interaction.message.edit(view=self)

        await interaction.response.send_message(f"✅ تم تأكيد تسديد المخالفة للمواطن <@{self.target_user_id}> بواسطة {interaction.user.mention}.", ephemeral=False)

        # التحقق مما إذا كان المواطن قد سدد جميع المخالفات لإزالة رتبة إيقاف الخدمات
        member = interaction.guild.get_member(self.target_user_id)
        if member:
            has_unpaid = any(not t.get("paid", False) for t in tickets)
            if not has_unpaid:
                overdue_role = interaction.guild.get_role(OVERDUE_ROLE_ID)
                if overdue_role and overdue_role in member.roles:
                    try:
                        await member.remove_roles(overdue_role)
                        await interaction.channel.send(f"🟢 **إلغاء إيقاف خدمات:** تم سداد جميع المخالفات بحق المواطن {member.mention} وتم رفع إيقاف الخدمات عنه بنجاح.")
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
            discord.SelectOption(label="عدم إفساح الطريق لمركبات الطوارئ", description="الغرامة: 2000 داركي", value="2000|عدم إفساح الطريق لمركبات الطوارئ"),
            discord.SelectOption(label="تعديل بدون تصريح (حجز/حرمان)", description="الغرامة: 10000 داركي", value="10000|تعديل بدون تصريح (حجز)"),
            discord.SelectOption(label="تفحيط (حجز)", description="الغرامة: 5000 داركي", value="5000|تفحيط (حجز)"),
            discord.SelectOption(label="زرة (حجز)", description="الغرامة: 2000 داركي", value="2000|زرة (حجز)"),
        ]

        super().__init__(placeholder="📋 اختر نوع المخالفة المرورية...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        amount, reason = self.values[0].split("|")
        amount = int(amount)

        users = load_users()
        user_key = str(self.target_member.id)

        if user_key not in users:
            users[user_key] = {
                "discord_tag": str(self.target_member),
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
            "proof_url": self.proof_url
        }
        users[user_key]["tickets"].append(ticket_data)
        save_users(users)

        ticket_index = len(users[user_key]["tickets"]) - 1

        embed = discord.Embed(
            title="🚔 وزارة الداخلية - إشعار مخالفة مرورية",
            description=f"تم إدخال مخالفة مرورية جديدة بحق المواطن {self.target_member.mention}.",
            color=0xe74c3c
        )
        embed.add_field(name="👤 المواطن المخالف", value=self.target_member.mention, inline=True)
        embed.add_field(name="🆔 رقم الهوية المرورية", value=f"`{self.rp_id}`", inline=True)
        embed.add_field(name="💰 قيمة الغرامة", value=f"**{amount:,} داركي**", inline=True)
        embed.add_field(name="📝 نوع المخالفة", value=f"`{reason}`", inline=False)
        embed.add_field(name="👮‍♂️ العسكري المحرر", value=f"{interaction.user.mention} (`{interaction.user.display_name}`)", inline=False)
        
        embed.set_image(url=self.proof_url)

        embed.add_field(
            name="🔴 ملاحظات هامة",
            value="• جهلك بالقوانين لا يرفع عنك العقوبة.\n"
                  "• المخالفات وُضعت للحفاظ على سلامتكم من خطر الطريق.\n"
                  "• ⚠️ **مهلة التسديد هي 7 أيام**، وفي حال عدم التسديد سيتم **إيقاف خدماتك** تلقائياً.\n"
                  "• في حال محاولة الهروب سيتم تحويلك للسجن مباشرة.",
            inline=False
        )
        embed.set_footer(text="وزارة الداخلية تتمنى لكم قيادة آمنة وسعيدة 📗")

        # إرسال المخالفة حصرياً في روم المخالفات مع زر تسديد المخالفة
        traffic_channel = interaction.guild.get_channel(TICKET_ALLOWED_CHANNEL_ID)
        if traffic_channel:
            pay_view = PayFineButton(self.target_member.id, ticket_index)
            await traffic_channel.send(
                content=f"📢 إشعار مخالفة موجه للمواطن: {self.target_member.mention}",
                embed=embed,
                view=pay_view
            )

        # إرسال نسخة على الخاص للمواطن
        try:
            await self.target_member.send(embed=embed)
        except discord.Forbidden:
            pass

        await interaction.followup.send(content=f"✅ تم تحرير المخالفة وإرسالها للمواطن {self.target_member.mention} في روم المخالفات بنجاح!", ephemeral=True)

class FineView(discord.ui.View):
    def __init__(self, target_member: discord.Member, rp_id: str, proof_url: str):
        super().__init__(timeout=60)
        self.add_item(FineSelect(target_member, rp_id, proof_url))

@bot.tree.command(name="مخالفة", description="تحرير مخالفة مرورية لمواطن (تتطلب إرفاق صورة الدليل)")
async def make_ticket(interaction: discord.Interaction, target: discord.Member, proof: discord.Attachment):
    if interaction.channel_id != TICKET_ALLOWED_CHANNEL_ID:
        allowed_channel = interaction.guild.get_channel(TICKET_ALLOWED_CHANNEL_ID)
        channel_mention = allowed_channel.mention if allowed_channel else f"<#{TICKET_ALLOWED_CHANNEL_ID}>"
        return await interaction.response.send_message(
            f"❌ **عفواً، لا يمكنك استخدام هذا الأمر هنا!**\nيرجى استخدام أمر المخالفات في الروم المخصصة فقط: {channel_mention}",
            ephemeral=True
        )

    staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
    if staff_role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ هذا الأمر مخصص لرجال الشرطة والإدارة فقط.", ephemeral=True)

    if not proof.content_type or not proof.content_type.startswith("image/"):
        return await interaction.response.send_message("❌ يجب إرفاق صورة دليل صالحة (PNG, JPG, WebP) للمخالفة!", ephemeral=True)

    users = load_users()
    user_data = users.get(str(target.id))
    rp_id = user_data.get("rp_id", "غير مسجل") if user_data else "غير مسجل"

    view = FineView(target, rp_id, proof.url)
    await interaction.response.send_message(
        content=f"👮‍♂️ جاري تحرير مخالفة للمواطن: {target.mention} (الهوية: `{rp_id}`)\nاختر نوع المخالفة من القائمة لإنهاء الإجراءات:",
        view=view,
        ephemeral=True
    )

# ==================== نظام المراجعة وإيقاف الخدمات ====================
@tasks.loop(hours=1)
async def check_overdue_tickets():
    guild = bot.get_guild(GUILD_ID)
    if not guild: return

    overdue_role = guild.get_role(OVERDUE_ROLE_ID)
    if not overdue_role: return

    users = load_users()
    now = datetime.now()

    for user_id_str, data in users.items():
        tickets = data.get("tickets", [])
        has_unpaid_overdue = False

        for ticket in tickets:
            if not ticket.get("paid", False):
                issued_at_str = ticket.get("issued_at")
                if issued_at_str:
                    issued_at = datetime.fromisoformat(issued_at_str)
                    if now - issued_at >= timedelta(days=7):
                        has_unpaid_overdue = True
                        break

        if has_unpaid_overdue:
            try:
                member = guild.get_member(int(user_id_str))
                if member and overdue_role not in member.roles:
                    await member.add_roles(overdue_role)
                    try:
                        embed_warn = discord.Embed(
                            title="⚠️ إشعار إيقاف خدمات",
                            description="لقد انقضت مهلة الـ 7 أيام لتسديد مخالفاتك المرورية دون تسديدها.\n"
                                        "تم تطبيق **إيقاف الخدمات** عليك في السيرفر، يرجى التوجه لإدارة المرور لتسوية وضعك وفك الإيقاف.",
                            color=discord.Color.dark_red()
                        )
                        await member.send(embed=embed_warn)
                    except: pass
            except Exception as e:
                logger.error(f"خطأ أثناء منح رتبة إيقاف الخدمات للعضو {user_id_str}: {e}")

# ==================== الأوامر والأحداث ====================
@bot.command()
@commands.has_permissions(administrator=True)
async def setup_apply(ctx):
    embed = discord.Embed(
        title="📝 تقديم طلب رول بلاي",
        description="اضغط الزر بالأسفل وقم بتعبئة نموذج التقديم.",
        color=discord.Color.blurple()
    )
    channel = bot.get_channel(APPLY_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed, view=ApplyView())
        await ctx.send("✅ تم إرسال رسالة التقديم.")

@bot.event
async def on_ready():
    bot.add_view(ApplyView())
    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ تم مزامنة {len(synced)} أمر سلاش بنجاح.")
    except Exception as e:
        logger.error(f"خطأ أثناء مزامنة أوامر السلاش: {e}")

    if not check_overdue_tickets.is_running():
        check_overdue_tickets.start()

    await bot.change_presence(status=discord.Status.online, activity=discord.CustomActivity(name="Distributing"))
    logger.info(f"✅ البوت شغال بنجاح باسم {bot.user}")

def run_bot():
    keep_alive()
    bot.run(TOKEN, log_handler=None)

if __name__ == "__main__": 
    run_bot()

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
            return await interaction.response.send_message("❌ عفواً، هذا الزر مخصص للمسؤولين المصرح لهم بتأكيد التسديد فقط!", ephemeral=True)

        users = load_users()
        user_key = str(self.target_user_id)

        if user_key not in users or "tickets" not in users[user_key]:
            return await interaction.response.send_message("❌ لم يتم العثور على سجل المخالفة هذا!", ephemeral=True)

        tickets = users[user_key]["tickets"]
        if self.ticket_index >= len(tickets):
            return await interaction.response.send_message("❌ المخالفة غير موجودة أو تم تسديدها سابقاً!", ephemeral=True)

        tickets[self.ticket_index]["paid"] = True
        save_users(users)

        button.disabled = True
        button.label = f"✅ تم التسديد بواسطة {interaction.user.display_name}"
        button.style = discord.ButtonStyle.secondary
        await interaction.message.edit(view=self)

        await interaction.response.send_message(f"✅ تم تأكيد تسديد المخالفة للمواطن <@{self.target_user_id}> بواسطة {interaction.user.mention}.", ephemeral=False)

        member = interaction.guild.get_member(self.target_user_id)
        if member:
            has_unpaid = any(not t.get("paid", False) for t in tickets)
            if not has_unpaid:
                overdue_role = interaction.guild.get_role(OVERDUE_ROLE_ID)
                if overdue_role and overdue_role in member.roles:
                    try:
                        await member.remove_roles(overdue_role)
                        await interaction.channel.send(f"🟢 **إلغاء إيقاف خدمات:** تم سداد جميع المخالفات بحق المواطن {member.mention} وتم رفع إيقاف الخدمات عنه بنجاح.")
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
            discord.SelectOption(label="عدم إفساح الطريق لمركبات الطوارئ", description="الغرامة: 2000 داركي", value="2000|عدم إفساح الطريق لمركبات الطوارئ"),
            discord.SelectOption(label="تعديل بدون تصريح (حجز/حرمان)", description="الغرامة: 10000 داركي", value="10000|تعديل بدون تصريح (حجز)"),
            discord.SelectOption(label="تفحيط (حجز)", description="الغرامة: 5000 داركي", value="5000|تفحيط (حجز)"),
            discord.SelectOption(label="زرة (حجز)", description="الغرامة: 2000 داركي", value="2000|زرة (حجز)"),
        ]

        super().__init__(placeholder="📋 اختر نوع المخالفة المرورية...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        amount, reason = self.values[0].split("|")
        amount = int(amount)

        users = load_users()
        user_key = str(self.target_member.id)

        if user_key not in users:
            users[user_key] = {
                "discord_tag": str(self.target_member),
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
            "proof_url": self.proof_url
        }
        users[user_key]["tickets"].append(ticket_data)
        save_users(users)

        ticket_index = len(users[user_key]["tickets"]) - 1

        embed = discord.Embed(
            title="🚔 وزارة الداخلية - إشعار مخالفة مرورية",
            description=f"تم إدخال مخالفة مرورية جديدة بحق المواطن {self.target_member.mention}.",
            color=0xe74c3c
        )
        embed.add_field(name="👤 المواطن المخالف", value=self.target_member.mention, inline=True)
        embed.add_field(name="🆔 رقم الهوية المرورية", value=f"`{self.rp_id}`", inline=True)
        embed.add_field(name="💰 قيمة الغرامة", value=f"**{amount:,} داركي**", inline=True)
        embed.add_field(name="📝 نوع المخالفة", value=f"`{reason}`", inline=False)
        embed.add_field(name="👮‍♂️ العسكري المحرر", value=f"{interaction.user.mention} (`{interaction.user.display_name}`)", inline=False)
        
        embed.set_image(url=self.proof_url)

        embed.add_field(
            name="🔴 ملاحظات هامة",
            value="• جهلك بالقوانين لا يرفع عنك العقوبة.\n"
                  "• المخالفات وُضعت للحفاظ على سلامتكم من خطر الطريق.\n"
                  "• ⚠️ **مهلة التسديد هي 7 أيام**، وفي حال عدم التسديد سيتم **إيقاف خدماتك** تلقائياً.\n"
                  "• في حال محاولة الهروب سيتم تحويلك للسجن مباشرة.",
            inline=False
        )
        embed.set_footer(text="وزارة الداخلية تتمنى لكم قيادة آمنة وسعيدة 📗")

        traffic_channel = interaction.guild.get_channel(TICKET_ALLOWED_CHANNEL_ID)
        if traffic_channel:
            pay_view = PayFineButton(self.target_member.id, ticket_index)
            await traffic_channel.send(
                content=f"📢 إشعار مخالفة موجه للمواطن: {self.target_member.mention}",
                embed=embed,
                view=pay_view
            )

        try:
            await self.target_member.send(embed=embed)
        except discord.Forbidden:
            pass

        await interaction.followup.send(content=f"✅ تم تحرير المخالفة وإرسالها للمواطن {self.target_member.mention} في روم المخالفات بنجاح!", ephemeral=True)


class FineView(discord.ui.View):
    def __init__(self, target_member: discord.Member, rp_id: str, proof_url: str):
        super().__init__(timeout=60)
        self.add_item(FineSelect(target_member, rp_id, proof_url))


@bot.tree.command(name="مخالفة", description="تحرير مخالفة مرورية لمواطن (تتطلب إرفاق صورة الدليل)")
async def make_ticket(interaction: discord.Interaction, target: discord.Member, proof: discord.Attachment):
    if interaction.channel_id != TICKET_ALLOWED_CHANNEL_ID:
        allowed_channel = interaction.guild.get_channel(TICKET_ALLOWED_CHANNEL_ID)
        channel_mention = allowed_channel.mention if allowed_channel else f"<#{TICKET_ALLOWED_CHANNEL_ID}>"
        return await interaction.response.send_message(
            f"❌ **عفواً، لا يمكنك استخدام هذا الأمر هنا!**\nيرجى استخدام أمر المخالفات في الروم المخصصة فقط: {channel_mention}",
            ephemeral=True
        )

    staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
    if staff_role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ هذا الأمر مخصص لرجال الشرطة والإدارة فقط.", ephemeral=True)

    if not proof.content_type or not proof.content_type.startswith("image/"):
        return await interaction.response.send_message("❌ يجب إرفاق صورة دليل صالحة (PNG, JPG, WebP) للمخالفة!", ephemeral=True)

    users = load_users()
    user_data = users.get(str(target.id))
    rp_id = user_data.get("rp_id", "غير مسجل") if user_data else "غير مسجل"

    view = FineView(target, rp_id, proof.url)
    await interaction.response.send_message(
        content=f"👮‍♂️ جاري تحرير مخالفة للمواطن: {target.mention} (الهوية: `{rp_id}`)\nاختر نوع المخالفة من القائمة لإنهاء الإجراءات:",
        view=view,
        ephemeral=True
    )


# ==================== نظام المراجعة وإيقاف الخدمات ====================
@tasks.loop(hours=1)
async def check_overdue_tickets():
    guild = bot.get_guild(GUILD_ID)
    if not guild: return

    overdue_role = guild.get_role(OVERDUE_ROLE_ID)
    if not overdue_role: return

    users = load_users()
    now = datetime.now()

    for user_id_str, data in users.items():
        tickets = data.get("tickets", [])
        has_unpaid_overdue = False

        for ticket in tickets:
            if not ticket.get("paid", False):
                issued_at_str = ticket.get("issued_at")
                if issued_at_str:
                    issued_at = datetime.fromisoformat(issued_at_str)
                    if now - issued_at >= timedelta(days=7):
                        has_unpaid_overdue = True
                        break

        if has_unpaid_overdue:
            try:
                member = guild.get_member(int(user_id_str))
                if member and overdue_role not in member.roles:
                    await member.add_roles(overdue_role)
                    try:
                        embed_warn = discord.Embed(
                            title="⚠️ إشعار إيقاف خدمات",
                            description="لقد انقضت مهلة الـ 7 أيام لتسديد مخالفاتك المرورية دون تسديدها.\n"
                                        "تم تطبيق **إيقاف الخدمات** عليك في السيرفر، يرجى التوجه لإدارة المرور لتسوية وضعك وفك الإيقاف.",
                            color=discord.Color.dark_red()
                        )
                        await member.send(embed=embed_warn)
                    except: pass
            except Exception as e:
                logger.error(f"خطأ أثناء منح رتبة إيقاف الخدمات للعضو {user_id_str}: {e}")

