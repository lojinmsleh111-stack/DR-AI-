import discord
from discord.ext import commands, tasks
import json
import os
from datetime import datetime, timedelta

DATA_FILE = "streaks.json"
STREAK_CHANNEL_ID = 123456789012345678  # 👈 استبدله بـ ID روم الستريك
FORBIDDEN_EMOJIS = ["🖕", "🍑", "🍆", "🖕🏻", "🖕🏼", "🖕🏽", "🖕🏾", "🖕🏿"]

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# نافذة إدخال الإيموجي (Modal)
class EmojiModal(discord.ui.Modal, title="تغيير إيموجي الستريك"):
    new_emoji = discord.ui.TextInput(
        label="أدخل الإيموجي الجديد",
        placeholder="ضع إيموجي واحد هنا (مثال: ⚡)",
        min_length=1,
        max_length=2
    )

    async def on_submit(self, interaction: discord.Interaction):
        emoji = self.new_emoji.value
        if any(forbidden in emoji for forbidden in FORBIDDEN_EMOJIS):
            await interaction.response.send_message("❌ هذا الإيموجي محظور وغير مسموح به!", ephemeral=True)
            return

        data = load_data()
        user_id = str(interaction.user.id)
        if user_id not in data:
            data[user_id] = {"count": 0, "last_post": "", "emoji": "🔥"}
        
        data[user_id]["emoji"] = emoji
        save_data(data)
        await interaction.response.send_message(f"✨ تم تحديث الإيموجي الخاص بك بنجاح إلى: {emoji}", ephemeral=True)

# زر تغيير الإيموجي المرفق مع الرسالة
class StreakView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="تغيير الإيموجي", style=discord.ButtonStyle.primary, emoji="✏️")
    async def change_emoji(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EmojiModal())

# الـ Cog الخاص بالستريك
class StreakCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_expired_streaks.start()

    def cog_unload(self):
        self.check_expired_streaks.cancel()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if message.channel.id == STREAK_CHANNEL_ID:
            has_image = any(att.content_type and att.content_type.startswith('image/') for att in message.attachments)
            
            if has_image:
                data = load_data()
                user_id = str(message.author.id)
                now = datetime.utcnow()

                if user_id not in data:
                    data[user_id] = {"count": 0, "last_post": "", "emoji": "🔥"}

                last_post_str = data[user_id].get("last_post", "")
                user_emoji = data[user_id].get("emoji", "🔥")

                if last_post_str:
                    last_time = datetime.fromisoformat(last_post_str)
                    time_diff = now - last_time

                    if time_diff < timedelta(hours=12):
                        embed = discord.Embed(
                            description=f"⚠️ {message.author.mention} لقد سجلت الستريك اليوم بالفعل! عد لاحقاً.",
                            color=discord.Color.gold()
                        )
                        await message.channel.send(embed=embed, delete_after=5)
                        return
                    elif time_diff <= timedelta(hours=48):
                        data[user_id]["count"] += 1
                    else:
                        data[user_id]["count"] = 1
                else:
                    data[user_id]["count"] = 1

                data[user_id]["last_post"] = now.isoformat()
                save_data(data)

                streak_count = data[user_id]["count"]

                embed = discord.Embed(
                    title=f"{user_emoji} تم تحديث الستريك! {user_emoji}",
                    description=f"كفو يا بطل {message.author.mention}! استمر في المحافظة على الستريك!",
                    color=discord.Color.orange()
                )
                embed.add_field(name="الستريك الحالي", value=f"```\n{user_emoji} {streak_count} أيام متتالية\n```", inline=False)
                embed.set_thumbnail(url=message.author.display_avatar.url)
                embed.set_footer(text="يمكنك تغيير الإيموجي من خلال الزر بالأسفل")

                msg = await message.channel.send(embed=embed, view=StreakView())
                try:
                    await msg.add_reaction(user_emoji)
                except Exception:
                    pass

    @commands.command(name="ستريك", aliases=["الستريك"])
    async def show_streak(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        data = load_data()
        user_id = str(member.id)

        user_data = data.get(user_id, {})
        streak_count = user_data.get("count", 0)
        user_emoji = user_data.get("emoji", "🔥")

        embed = discord.Embed(
            title=f"📊 إحصائيات الستريك لـ {member.display_name}",
            color=discord.Color.orange()
        )
        embed.add_field(name="عدد الأيام المتتالية", value=f"### {user_emoji} {streak_count} يوم", inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        
        await ctx.send(embed=embed)

    @commands.command(name="تعيين_إيموجي", aliases=["تعيين_ايموجي"])
    async def set_emoji(self, ctx, new_emoji: str):
        if any(forbidden in new_emoji for forbidden in FORBIDDEN_EMOJIS):
            embed = discord.Embed(
                title="❌ إيموجي غير مسموح",
                description="عذراً، هذا الإيموجي محظور واستخدامه غير مسموح!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        data = load_data()
        user_id = str(ctx.author.id)

        if user_id not in data:
            data[user_id] = {"count": 0, "last_post": "", "emoji": "🔥"}

        data[user_id]["emoji"] = new_emoji
        save_data(data)

        embed = discord.Embed(
            title="✨ تم تغيير الإيموجي بنجاح",
            description=f"تم تعيين الإيموجي الخاص بك إلى: {new_emoji}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @tasks.loop(hours=1)
    async def check_expired_streaks(self):
        data = load_data()
        now = datetime.utcnow()
        updated = False

        for user_id, info in list(data.items()):
            if info.get("last_post"):
                last_time = datetime.fromisoformat(info["last_post"])
                if now - last_time > timedelta(hours=48):
                    if info["count"] > 0:
                        info["count"] = 0
                        updated = True

        if updated:
            save_data(data)

async def setup(bot):
    await bot.add_cog(StreakCog(bot))
    
