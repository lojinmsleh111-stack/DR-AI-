class ApplyModal(discord.ui.Modal, title="تقديم طلب تصريح رول بلاي"):
    q1 = discord.ui.TextInput(
        label="الاسم الكريم:",
        placeholder="أدخل اسمك...",
        required=True,
        max_length=100
    )
    q2 = discord.ui.TextInput(
        label="عمرك الحقيقي:",
        placeholder=" الرجاء وضع عمرك الحقيقي",
        required=True,
        max_length=10
    )
    q3 = discord.ui.TextInput(
        label="اسم حسابك الأساسي في روبلوكس:",
        placeholder="Username...",
        required=True,
        max_length=100
    )
    q4 = discord.ui.TextInput(
        label="اختصار الحساب:",
        placeholder="Display Name / اليوزر...",
        required=True,
        max_length=100
    )
    q5 = discord.ui.TextInput(
        label="قسم التعهد بالالتزام بقوانين السيرفر والاحترام:",
        style=discord.TextStyle.paragraph,
        placeholder="اكتب القسم هنا...",
        required=True,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ تم إرسال طلبك بنجاح! سيتم مراجعته من قبل إدارة الرول بلاي.", ephemeral=True)

        review_channel = interaction.guild.get_channel(REVIEW_CHANNEL_ID)
        if review_channel:
            embed = discord.Embed(
                title="📑 طلب تصريح رول بلاي جديد",
                description=f"قدم المواطن {interaction.user.mention} طلب للحصول على التصريح.",
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            embed.add_field(name="👤 العضو", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
            embed.add_field(name="1️⃣ الاسم الكريم:", value=self.q1.value, inline=False)
            embed.add_field(name="2️⃣ عمرك الحقيقي:", value=self.q2.value, inline=True)
            embed.add_field(name="3️⃣ اسم حسابك الأساسي في روبلوكس:", value=f"`{self.q3.value}`", inline=True)
            embed.add_field(name="4️⃣ اختصار الحساب:", value=f"`{self.q4.value}`", inline=True)
            embed.add_field(name="5️⃣ قسم التعهد بالالتزام بقوانين السيرفر واحترام الإدارة والأعضاء:", value=self.q5.value, inline=False)
            embed.set_footer(text="استخدم الأزرار بالأسفل قبول أو رفض الطلب")

            view = RPReviewButtons(applicant_id=interaction.user.id, char_name=self.q1.value)
            await review_channel.send(embed=embed, view=view)
            
