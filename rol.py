import discord
from discord.ext import commands

OWNER_ID = 449133974867017728
bot_reference = None


class RoleSelect(discord.ui.Select):
    def __init__(self, member):
        self.member = member
        roles = [r for r in member.guild.roles if r != member.guild.default_role and not r.managed]
        roles = list(reversed(roles))[:25]

        options = [
            discord.SelectOption(
                label=r.name[:100],
                value=str(r.id),
                description="Yönetici yetkili rol" if r.permissions.administrator else "Normal rol"
            )
            for r in roles
        ]

        super().__init__(
            placeholder="🎭 Vermek istediğin rolü seç...",
            options=options or [discord.SelectOption(label="Rol yok", value="0")]
        )

    async def callback(self, interaction):
        if self.values[0] == "0":
            return await interaction.response.send_message("❌ Verilebilir rol yok.", ephemeral=True)

        guild = interaction.guild
        role = guild.get_role(int(self.values[0]))

        if not role:
            return await interaction.response.send_message("❌ Rol bulunamadı.", ephemeral=True)

        bot_member = guild.me
        if not bot_member or role >= bot_member.top_role:
            return await interaction.response.send_message(
                "❌ Bu rol botun en yüksek rolüyle aynı seviyede veya üstünde.",
                ephemeral=True
            )

        # ==========================================
        # NORMAL ROL -> DİREKT VER
        # YÖNETİCİ ROL -> OWNER ONAYI
        # ==========================================

        if not role.permissions.administrator:
            try:
                await self.member.add_roles(
                    role,
                    reason=f"{interaction.user} tarafından rolver komutu ile verildi."
                )
            except discord.Forbidden:
                return await interaction.response.send_message(
                    "❌ Discord bu rolü vermeme izin vermedi. Botun rolünü kontrol et.",
                    ephemeral=True
                )
            except discord.HTTPException as e:
                return await interaction.response.send_message(
                    f"❌ Discord hatası: `HTTP {e.status}`",
                    ephemeral=True
                )

            return await interaction.response.send_message(
                f"✅ **{role.name}** rolü **{self.member}** kullanıcısına verildi.",
                ephemeral=True
            )

        # ==========================================
        # YÖNETİCİ ROLÜ -> OWNER ONAYI
        # ==========================================

        if owner is None:
            try:
                owner = await bot_reference.fetch_user(OWNER_ID)
            except Exception:
                owner = None

        if owner is None:
            return await interaction.response.send_message(
                "❌ Owner bulunamadı.", ephemeral=True
            )

        embed = discord.Embed(
            title="⚠️ Yönetici Rolü Onayı",
            description="Bir kullanıcıya **Yönetici yetkili rol** verilmek isteniyor.",
            color=discord.Color.orange()
        )
        embed.add_field(name="👤 Kullanıcı", value=f"{self.member.mention}\n`{self.member.id}`", inline=False)
        embed.add_field(name="🎭 Rol", value=f"**{role.name}**\n`{role.id}`", inline=False)
        embed.add_field(name="🏠 Sunucu", value=f"**{guild.name}**\n`{guild.id}`", inline=False)
        embed.add_field(name="👮 Talep eden", value=f"{interaction.user.mention}\n`{interaction.user.id}`", inline=False)

        try:
            await owner.send(
                embed=embed,
                view=RoleApprovalView(guild.id, self.member.id, role.id)
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ Owner'ın DM'leri kapalı.", ephemeral=True
            )

        await interaction.response.send_message(
            f"📨 **{role.name}** için Owner'a onay isteği gönderildi.",
            ephemeral=True
        )


class RoleSelectView(discord.ui.View):
    def __init__(self, member):
        super().__init__(timeout=60)
        self.add_item(RoleSelect(member))


class RoleApprovalView(discord.ui.View):
    def __init__(self, guild_id, member_id, role_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.member_id = member_id
        self.role_id = role_id

    @discord.ui.button(label="Onayla", emoji="✅", style=discord.ButtonStyle.success)
    async def approve(self, interaction, button):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(
                "❌ Bu onayı sadece Owner kullanabilir.", ephemeral=True
            )

        guild = bot_reference.get_guild(self.guild_id)
        if guild is None:
            try:
                guild = await bot_reference.fetch_guild(self.guild_id)
            except Exception:
                guild = None

        if guild is None:
            return await interaction.response.send_message(
                "❌ Bot artık bu sunucuda değil veya sunucu bulunamadı.",
                ephemeral=True
            )

        role = guild.get_role(self.role_id)
        if role is None:
            try:
                role = await guild.fetch_role(self.role_id)
            except Exception:
                role = None

        if role is None:
            return await interaction.response.send_message(
                "❌ Rol artık bulunmuyor.", ephemeral=True
            )

        # ÖNEMLİ: get_member yoksa API'dan fetch_member yapıyoruz.
        member = guild.get_member(self.member_id)
        if member is None:
            try:
                member = await guild.fetch_member(self.member_id)
            except discord.NotFound:
                member = None
            except discord.Forbidden:
                return await interaction.response.send_message(
                    "❌ Kullanıcının sunucudaki üyelik bilgisine erişilemiyor.",
                    ephemeral=True
                )
            except discord.HTTPException as e:
                return await interaction.response.send_message(
                    f"❌ Discord hatası: `HTTP {e.status}`",
                    ephemeral=True
                )

        if member is None:
            return await interaction.response.send_message(
                "❌ Kullanıcı artık bu sunucuda değil.",
                ephemeral=True
            )

        bot_member = guild.me
        if bot_member is None:
            try:
                bot_member = await guild.fetch_member(bot_reference.user.id)
            except Exception:
                bot_member = None

        if bot_member is None or role >= bot_member.top_role:
            return await interaction.response.send_message(
                "❌ Bot bu rolü veremiyor. Botun rolünü seçilen rolün üstüne taşı.",
                ephemeral=True
            )

        try:
            await member.add_roles(
                role,
                reason="Owner tarafından yönetici rolü onaylandı."
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ Discord rolü vermeme izin vermedi. Bot rolünü yükselt.",
                ephemeral=True
            )
        except discord.HTTPException as e:
            return await interaction.response.send_message(
                f"❌ Discord hatası: `HTTP {e.status}`",
                ephemeral=True
            )

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=f"✅ **Onaylandı.**\n👤 {member}\n🎭 **{role.name}** rolü verildi.",
            embed=None,
            view=self
        )

    @discord.ui.button(label="Reddet", emoji="❌", style=discord.ButtonStyle.danger)
    async def reject(self, interaction, button):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(
                "❌ Bu işlemi sadece Owner kullanabilir.", ephemeral=True
            )

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content="❌ Yönetici rolü verme isteği reddedildi.",
            embed=None,
            view=self
        )


def setup(bot):
    global bot_reference
    bot_reference = bot

    @bot.command(name="rolver")
    @commands.guild_only()
    async def rolver(ctx, user_id: int = None):
        if user_id is None:
            return await ctx.send("❌ Kullanım: `.rolver <kullanıcı ID>`")

        member = ctx.guild.get_member(user_id)

        # Cache'de yoksa API'dan çek
        if member is None:
            try:
                member = await ctx.guild.fetch_member(user_id)
            except discord.NotFound:
                return await ctx.send("❌ Bu kullanıcı bu sunucuda değil.")
            except discord.Forbidden:
                return await ctx.send("❌ Kullanıcının bilgisine erişemiyorum.")
            except discord.HTTPException as e:
                return await ctx.send(f"❌ Discord hatası: `HTTP {e.status}`")

        roles = [
            r for r in ctx.guild.roles
            if r != ctx.guild.default_role and not r.managed
        ]

        if not roles:
            return await ctx.send("❌ Verilebilir rol yok.")

        await ctx.send(
            f"🎭 **{member}** için vermek istediğin rolü seç:",
            view=RoleSelectView(member)
        )