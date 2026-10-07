import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta
import re

# ============================================================
# AYARLAR
# ============================================================

OWNER_ID = 449133974867017728

bot_reference = None

# Geçici warn kayıtları
warnings = {}


# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

async def get_member(guild, user_input):
    """
    Mention veya ID ile kullanıcı bulur.
    Örnek:
    @Kullanıcı
    123456789012345678
    """

    user_input = user_input.strip()

    # <@123> veya <@!123>
    match = re.match(r"<@!?(\d+)>$", user_input)

    if match:
        user_id = int(match.group(1))
    elif user_input.isdigit():
        user_id = int(user_input)
    else:
        return None

    member = guild.get_member(user_id)

    if member:
        return member

    try:
        return await guild.fetch_member(user_id)
    except (discord.NotFound, discord.HTTPException):
        return None


def hierarchy_error(ctx, target):
    """Rol hiyerarşisi kontrolü."""

    if target.id == ctx.author.id:
        return "❌ Kendin üzerinde bu işlemi yapamazsın."

    if target.id == ctx.guild.owner_id:
        return "❌ Sunucu sahibine bu işlemi uygulayamazsın."

    if target.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
        return "❌ Senden yüksek veya eşit role sahip kullanıcıya işlem yapamazsın."

    if target.top_role >= ctx.guild.me.top_role:
        return "❌ Botun rolü bu kullanıcıdan yüksek olmalı."

    return None


def parse_duration(duration):
    """
    10s
    10m
    2h
    3d

    şeklindeki süreleri timedelta'a çevirir.
    """

    match = re.fullmatch(r"(\d+)(s|m|h|d)", duration.lower())

    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2)

    if unit == "s":
        return timedelta(seconds=amount)

    if unit == "m":
        return timedelta(minutes=amount)

    if unit == "h":
        return timedelta(hours=amount)

    if unit == "d":
        return timedelta(days=amount)

    return None


# ============================================================
# BAN ONAY PANELİ
# ============================================================

class BanApprovalView(discord.ui.View):

    def __init__(self, guild_id, target_id, requester_id):
        super().__init__(timeout=120)

        self.guild_id = guild_id
        self.target_id = target_id
        self.requester_id = requester_id
        self.finished = False

    @discord.ui.button(
        label="BANLA",
        emoji="🔨",
        style=discord.ButtonStyle.danger
    )
    async def approve(self, interaction: discord.Interaction, button):

        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message(
                "❌ Bu paneli sadece bot sahibi kullanabilir.",
                ephemeral=True
            )
            return

        if self.finished:
            await interaction.response.send_message(
                "❌ Bu istek zaten sonuçlandırıldı.",
                ephemeral=True
            )
            return

        self.finished = True

        guild = bot_reference.get_guild(self.guild_id)

        if not guild:
            await interaction.response.edit_message(
                content="❌ Sunucu bulunamadı.",
                view=None
            )
            return

        try:
            target = await guild.fetch_member(self.target_id)
        except discord.NotFound:
            target = None
        except Exception as e:
            await interaction.response.edit_message(
                content=(
                    "❌ Kullanıcı kontrol edilemedi.\n"
                    f"`{type(e).__name__}: {e}`"
                ),
                view=None
            )
            return

        if not target:
            await interaction.response.edit_message(
                content="❌ Bu kullanıcı artık sunucuda değil.",
                view=None
            )
            return

        try:

            await guild.ban(
                target,
                reason="Bot sahibi onayı",
                delete_message_days=0
            )

            await interaction.response.edit_message(
                content=(
                    "🔨 **KULLANICI BANLANDI**\n\n"
                    f"👤 Kullanıcı: **{target}**\n"
                    f"🆔 ID: `{target.id}`\n"
                    f"🏠 Sunucu: **{guild.name}**"
                ),
                view=None
            )

            requester = guild.get_member(self.requester_id)

            if requester:
                try:
                    await requester.send(
                        "🔨 **Ban isteğin onaylandı.**\n"
                        f"👤 Kullanıcı: **{target}**"
                    )
                except discord.Forbidden:
                    pass

        except discord.Forbidden:

            await interaction.response.edit_message(
                content=(
                    "❌ **BAN BAŞARISIZ**\n\n"
                    "Botun bu kullanıcıyı banlama yetkisi yok."
                ),
                view=None
            )

        except Exception as e:

            await interaction.response.edit_message(
                content=(
                    "❌ Ban sırasında hata oluştu:\n"
                    f"`{type(e).__name__}: {e}`"
                ),
                view=None
            )

    @discord.ui.button(
        label="REDDET",
        emoji="❌",
        style=discord.ButtonStyle.secondary
    )
    async def reject(self, interaction: discord.Interaction, button):

        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message(
                "❌ Bu paneli sadece bot sahibi kullanabilir.",
                ephemeral=True
            )
            return

        if self.finished:
            await interaction.response.send_message(
                "❌ Bu istek zaten sonuçlandırıldı.",
                ephemeral=True
            )
            return

        self.finished = True

        await interaction.response.edit_message(
            content="❌ **BAN İSTEĞİ REDDEDİLDİ.**",
            view=None
        )

        guild = bot_reference.get_guild(self.guild_id)

        if guild:

            requester = guild.get_member(self.requester_id)

            if requester:
                try:
                    await requester.send(
                        "❌ **Ban isteğin reddedildi.**"
                    )
                except discord.Forbidden:
                    pass


# ============================================================
# UNBAN ONAY PANELİ
# ============================================================

class UnbanApprovalView(discord.ui.View):

    def __init__(self, guild_id, target_id, requester_id):
        super().__init__(timeout=120)

        self.guild_id = guild_id
        self.target_id = target_id
        self.requester_id = requester_id
        self.finished = False

    @discord.ui.button(
        label="UNBAN",
        emoji="🔓",
        style=discord.ButtonStyle.success
    )
    async def approve(self, interaction: discord.Interaction, button):

        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message(
                "❌ Bu paneli sadece bot sahibi kullanabilir.",
                ephemeral=True
            )
            return

        if self.finished:
            await interaction.response.send_message(
                "❌ Bu istek zaten sonuçlandırıldı.",
                ephemeral=True
            )
            return

        self.finished = True

        guild = bot_reference.get_guild(self.guild_id)

        if not guild:
            await interaction.response.edit_message(
                content="❌ Sunucu bulunamadı.",
                view=None
            )
            return

        try:

            user = await bot_reference.fetch_user(self.target_id)

            await guild.unban(
                user,
                reason="Bot sahibi onayı"
            )

            await interaction.response.edit_message(
                content=(
                    "🔓 **UNBAN YAPILDI**\n\n"
                    f"👤 Kullanıcı: **{user}**\n"
                    f"🆔 ID: `{user.id}`\n"
                    f"🏠 Sunucu: **{guild.name}**"
                ),
                view=None
            )

            requester = guild.get_member(self.requester_id)

            if requester:
                try:
                    await requester.send(
                        "🔓 **Unban isteğin onaylandı.**\n"
                        f"👤 Kullanıcı: **{user}**"
                    )
                except discord.Forbidden:
                    pass

        except discord.NotFound:

            await interaction.response.edit_message(
                content=(
                    "❌ Bu ID'ye sahip kullanıcı bulunamadı "
                    "veya kullanıcı banlı değil."
                ),
                view=None
            )

        except discord.Forbidden:

            await interaction.response.edit_message(
                content="❌ Botun bu sunucuda unban yetkisi yok.",
                view=None
            )

        except Exception as e:

            await interaction.response.edit_message(
                content=(
                    "❌ Unban sırasında hata oluştu:\n"
                    f"`{type(e).__name__}: {e}`"
                ),
                view=None
            )

    @discord.ui.button(
        label="REDDET",
        emoji="❌",
        style=discord.ButtonStyle.secondary
    )
    async def reject(self, interaction: discord.Interaction, button):

        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message(
                "❌ Bu paneli sadece bot sahibi kullanabilir.",
                ephemeral=True
            )
            return

        if self.finished:
            await interaction.response.send_message(
                "❌ Bu istek zaten sonuçlandırıldı.",
                ephemeral=True
            )
            return

        self.finished = True

        await interaction.response.edit_message(
            content="❌ **UNBAN İSTEĞİ REDDEDİLDİ.**",
            view=None
        )

        guild = bot_reference.get_guild(self.guild_id)

        if guild:

            requester = guild.get_member(self.requester_id)

            if requester:
                try:
                    await requester.send(
                        "❌ **Unban isteğin reddedildi.**"
                    )
                except discord.Forbidden:
                    pass


# ============================================================
# BAN İSTEĞİ
# ============================================================

async def create_ban_request(ctx, target):

    if target.id == ctx.author.id:
        await ctx.send("❌ Kendini banlayamazsın.")
        return

    if target.bot:
        await ctx.send(
            "❌ Bot hesaplarını bu komutla banlayamazsın."
        )
        return

    owner = bot_reference.get_user(OWNER_ID)

    if not owner:
        try:
            owner = await bot_reference.fetch_user(OWNER_ID)
        except Exception:
            await ctx.send("❌ Bot sahibine ulaşılamadı.")
            return

    embed = discord.Embed(
        title="🚨 BAN ONAYI GEREKİYOR",
        description=(
            "Bir kullanıcı için ban isteği geldi.\n\n"
            f"👤 **Banlanacak:** {target.mention}\n"
            f"🆔 **ID:** `{target.id}`\n\n"
            f"👮 **İsteği yapan:** {ctx.author.mention}\n"
            f"🏠 **Sunucu:** {ctx.guild.name}\n"
            f"🆔 **Sunucu ID:** `{ctx.guild.id}`\n\n"
            "Banlamak için aşağıdaki butona bas."
        ),
        color=discord.Color.red()
    )

    embed.set_footer(
        text="PwoxAI • Ban Güvenlik Sistemi"
    )

    view = BanApprovalView(
        ctx.guild.id,
        target.id,
        ctx.author.id
    )

    try:
        await owner.send(
            embed=embed,
            view=view
        )
    except discord.Forbidden:
        await ctx.send(
            "❌ Sana DM gönderemiyorum."
        )
        return

    await ctx.send(
        "📨 **Ban isteği sana DM olarak gönderildi.**\n"
        "⏳ Onayın bekleniyor."
    )


# ============================================================
# UNBAN İSTEĞİ
# ============================================================

async def create_unban_request(ctx, user_id):

    try:
        target_id = int(user_id)
    except ValueError:

        await ctx.send(
            "❌ Geçerli bir Discord ID gir.\n"
            "Örnek: `.unban 123456789012345678`"
        )
        return

    try:
        target = await bot_reference.fetch_user(target_id)

    except discord.NotFound:

        await ctx.send(
            "❌ Bu ID'ye sahip Discord kullanıcısı bulunamadı."
        )
        return

    except Exception as e:

        await ctx.send(
            f"❌ Kullanıcı bulunamadı: "
            f"`{type(e).__name__}`"
        )
        return

    owner = bot_reference.get_user(OWNER_ID)

    if not owner:

        try:
            owner = await bot_reference.fetch_user(OWNER_ID)
        except Exception:

            await ctx.send(
                "❌ Bot sahibine ulaşılamadı."
            )
            return

    embed = discord.Embed(
        title="🚨 UNBAN ONAYI GEREKİYOR",
        description=(
            "Bir kullanıcının banını kaldırmak için istek geldi.\n\n"
            f"👤 **Kullanıcı:** {target}\n"
            f"🆔 **ID:** `{target.id}`\n"
            f"🏠 **Sunucu:** {ctx.guild.name}\n"
            f"🆔 **Sunucu ID:** `{ctx.guild.id}`\n\n"
            f"👮 **İsteği yapan:** {ctx.author.mention}\n\n"
            "Banı kaldırmak için aşağıdaki butona bas."
        ),
        color=discord.Color.green()
    )

    embed.set_thumbnail(
        url=target.display_avatar.url
    )

    embed.set_footer(
        text="PwoxAI • Unban Güvenlik Sistemi"
    )

    view = UnbanApprovalView(
        ctx.guild.id,
        target.id,
        ctx.author.id
    )

    try:
        await owner.send(
            embed=embed,
            view=view
        )

    except discord.Forbidden:

        await ctx.send(
            "❌ Sana DM gönderemiyorum."
        )
        return

    await ctx.send(
        "📨 **Unban isteği sana DM olarak gönderildi.**\n"
        "⏳ Onayın bekleniyor."
    )


# ============================================================
# SETUP
# ============================================================

def setup(bot):

    global bot_reference

    bot_reference = bot

    # ========================================================
    # BAN
    # ========================================================

    @bot.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban_command(ctx, target_input=None):

        if not target_input:

            await ctx.send(
                "❌ Kullanıcı belirtmelisin.\n"
                "Örnek: `.ban @Kullanıcı`\n"
                "veya `.ban 123456789012345678`"
            )
            return

        target = await get_member(
            ctx.guild,
            target_input
        )

        if not target:

            await ctx.send(
                "❌ Kullanıcı bulunamadı."
            )
            return

        await create_ban_request(
            ctx,
            target
        )

    @ban_command.error
    async def ban_command_error(ctx, error):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            await ctx.send(
                "❌ Bu komut için **Üyeleri Yasakla** "
                "yetkisi gerekiyor."
            )
            return

        await ctx.send(
            f"❌ Hata: `{type(error).__name__}`"
        )


    # ========================================================
    # UNBAN
    # ========================================================

    @bot.command(name="unban")
    @commands.has_permissions(ban_members=True)
    async def unban_command(
        ctx,
        user_id: str = None
    ):

        if not user_id:

            await ctx.send(
                "❌ Kullanıcı ID'si girmelisin.\n"
                "Örnek:\n"
                "`.unban 123456789012345678`"
            )
            return

        await create_unban_request(
            ctx,
            user_id
        )

    @unban_command.error
    async def unban_command_error(ctx, error):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            await ctx.send(
                "❌ Bu komut için **Üyeleri Yasakla** "
                "yetkisi gerekiyor."
            )
            return

        await ctx.send(
            f"❌ Hata: `{type(error).__name__}`"
        )


    # ========================================================
    # KICK
    # .kick @user sebep
    # .kick ID sebep
    # ========================================================

    @bot.command(name="kick")
    @commands.has_permissions(kick_members=True)
    async def kick_command(
        ctx,
        target_input=None,
        *,
        reason="Belirtilmedi"
    ):

        if not target_input:

            await ctx.send(
                "❌ Kullanıcı belirtmelisin.\n"
                "Örnek: `.kick @Kullanıcı Spam`"
            )
            return

        target = await get_member(
            ctx.guild,
            target_input
        )

        if not target:

            await ctx.send(
                "❌ Kullanıcı bulunamadı."
            )
            return

        error = hierarchy_error(
            ctx,
            target
        )

        if error:

            await ctx.send(error)
            return

        try:

            await target.kick(
                reason=f"{ctx.author}: {reason}"
            )

            await ctx.send(
                f"👢 **{target}** sunucudan atıldı.\n"
                f"📝 Sebep: **{reason}**"
            )

        except discord.Forbidden:

            await ctx.send(
                "❌ Botun bu kullanıcıyı atlama yetkisi yok."
            )


    # ========================================================
    # TIMEOUT
    # .timeout @user 10m sebep
    # ========================================================

    @bot.command(name="mute")
    @commands.has_permissions(moderate_members=True)
    async def timeout_command(
        ctx,
        target_input=None,
        duration=None,
        *,
        reason="Belirtilmedi"
    ):

        if not target_input or not duration:

            await ctx.send(
                "❌ Kullanıcı ve süre belirtmelisin.\n\n"
                "Örnek:\n"
                "`.timeout @Kullanıcı 10m Spam`\n"
                "`.timeout 123456789 1h Reklam`"
            )
            return

        target = await get_member(
            ctx.guild,
            target_input
        )

        if not target:

            await ctx.send(
                "❌ Kullanıcı bulunamadı."
            )
            return

        error = hierarchy_error(
            ctx,
            target
        )

        if error:

            await ctx.send(error)
            return

        delta = parse_duration(
            duration
        )

        if not delta:

            await ctx.send(
                "❌ Geçersiz süre.\n"
                "Kullanım: `10s`, `10m`, `2h`, `3d`"
            )
            return

        if delta > timedelta(days=28):

            await ctx.send(
                "❌ Timeout en fazla **28 gün** olabilir."
            )
            return

        try:

            await target.timeout(
                delta,
                reason=f"{ctx.author}: {reason}"
            )

            await ctx.send(
                f"⏳ **{target}** timeoutlandı.\n"
                f"🕐 Süre: **{duration}**\n"
                f"📝 Sebep: **{reason}**"
            )

        except discord.Forbidden:

            await ctx.send(
                "❌ Botun bu kullanıcıya timeout uygulama yetkisi yok."
            )


    # ========================================================
    # UNTIMEOUT
    # ========================================================

    @bot.command(name="unmute")
    @commands.has_permissions(moderate_members=True)
    async def untimeout_command(
        ctx,
        target_input=None
    ):

        if not target_input:

            await ctx.send(
                "❌ Kullanıcı belirtmelisin.\n"
                "Örnek: `.untimeout @Kullanıcı`"
            )
            return

        target = await get_member(
            ctx.guild,
            target_input
        )

        if not target:

            await ctx.send(
                "❌ Kullanıcı bulunamadı."
            )
            return

        error = hierarchy_error(
            ctx,
            target
        )

        if error:

            await ctx.send(error)
            return

        try:

            await target.timeout(
                None,
                reason=f"{ctx.author} timeout kaldırdı"
            )

            await ctx.send(
                f"🔓 **{target}** kullanıcısının timeoutu kaldırıldı."
            )

        except discord.Forbidden:

            await ctx.send(
                "❌ Timeout kaldırılamadı."
            )


    # ========================================================
    # WARN
    # .warn @user sebep
    # ========================================================

    @bot.command(name="warn")
    @commands.has_permissions(moderate_members=True)
    async def warn_command(
        ctx,
        target_input=None,
        *,
        reason="Belirtilmedi"
    ):

        if not target_input:

            await ctx.send(
                "❌ Kullanıcı belirtmelisin.\n"
                "Örnek: `.warn @Kullanıcı Küfür`"
            )
            return

        target = await get_member(
            ctx.guild,
            target_input
        )

        if not target:

            await ctx.send(
                "❌ Kullanıcı bulunamadı."
            )
            return

        error = hierarchy_error(
            ctx,
            target
        )

        if error:

            await ctx.send(error)
            return

        guild_warnings = warnings.setdefault(
            ctx.guild.id,
            {}
        )

        user_warnings = guild_warnings.setdefault(
            target.id,
            []
        )

        user_warnings.append({
            "reason": reason,
            "moderator": ctx.author.id
        })

        count = len(user_warnings)

        await ctx.send(
            f"⚠️ **{target}** uyarıldı.\n"
            f"📝 Sebep: **{reason}**\n"
            f"📊 Toplam uyarı: **{count}**"
        )

        try:

            await target.send(
                f"⚠️ **{ctx.guild.name}** sunucusunda uyarıldın.\n"
                f"📝 Sebep: **{reason}**"
            )

        except discord.Forbidden:
            pass


    # ========================================================
    # WARNINGS
    # ========================================================

    @bot.command(name="uyarılar")
    @commands.has_permissions(moderate_members=True)
    async def warnings_command(
        ctx,
        target_input=None
    ):

        if not target_input:

            await ctx.send(
                "❌ Kullanıcı belirtmelisin.\n"
                "Örnek: `.warnings @Kullanıcı`"
            )
            return

        target = await get_member(
            ctx.guild,
            target_input
        )

        if not target:

            await ctx.send(
                "❌ Kullanıcı bulunamadı."
            )
            return

        guild_warnings = warnings.get(
            ctx.guild.id,
            {}
        )

        user_warnings = guild_warnings.get(
            target.id,
            []
        )

        if not user_warnings:

            await ctx.send(
                f"✅ **{target}** kullanıcısının uyarısı yok."
            )
            return

        embed = discord.Embed(
            title="⚠️ Kullanıcı Uyarıları",
            description=(
                f"👤 Kullanıcı: {target.mention}\n"
                f"🆔 ID: `{target.id}`\n"
                f"📊 Toplam: **{len(user_warnings)}**"
            ),
            color=discord.Color.orange()
        )

        for index, warning in enumerate(
            user_warnings,
            start=1
        ):

            moderator = ctx.guild.get_member(
                warning["moderator"]
            )

            moderator_text = (
                moderator.mention
                if moderator
                else f"`{warning['moderator']}`"
            )

            embed.add_field(
                name=f"Uyarı #{index}",
                value=(
                    f"📝 Sebep: {warning['reason']}\n"
                    f"👮 Yetkili: {moderator_text}"
                ),
                inline=False
            )

        await ctx.send(
            embed=embed
        )


    # ========================================================
    # CLEARWARNS
    # ========================================================

    @bot.command(name="clearwarns")
    @commands.has_permissions(moderate_members=True)
    async def clearwarns_command(
        ctx,
        target_input=None
    ):

        if not target_input:

            await ctx.send(
                "❌ Kullanıcı belirtmelisin.\n"
                "Örnek: `.clearwarns @Kullanıcı`"
            )
            return

        target = await get_member(
            ctx.guild,
            target_input
        )

        if not target:

            await ctx.send(
                "❌ Kullanıcı bulunamadı."
            )
            return

        guild_warnings = warnings.setdefault(
            ctx.guild.id,
            {}
        )

        if target.id not in guild_warnings:

            await ctx.send(
                "ℹ️ Bu kullanıcının zaten uyarısı yok."
            )
            return

        del guild_warnings[target.id]

        await ctx.send(
            f"🧹 **{target}** kullanıcısının tüm uyarıları silindi."
        )


    # ========================================================
    # CLEAR / SİL
    # ========================================================

    @bot.command(
        name="clear",
        aliases=["sil"]
    )
    @commands.has_permissions(manage_messages=True)
    async def clear_command(
        ctx,
        amount: int = None
    ):

        if amount is None:

            await ctx.send(
                "❌ Kaç mesaj silineceğini yaz.\n"
                "Örnek: `.clear 50`"
            )
            return

        if amount < 1:

            await ctx.send(
                "❌ En az 1 mesaj silebilirsin."
            )
            return

        if amount > 100:

            await ctx.send(
                "❌ Tek seferde en fazla 100 mesaj silebilirsin."
            )
            return

        try:

            deleted = await ctx.channel.purge(
                limit=amount + 1
            )

            message = await ctx.send(
                f"🧹 **{len(deleted) - 1}** mesaj silindi."
            )

            await message.delete(
                delay=3
            )

        except discord.Forbidden:

            await ctx.send(
                "❌ Botun mesaj silme yetkisi yok."
            )


    # ========================================================
    # LOCK
    # ========================================================

    @bot.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    async def lock_command(ctx):

        overwrite = ctx.channel.overwrites_for(
            ctx.guild.default_role
        )

        overwrite.send_messages = False

        await ctx.channel.set_permissions(
            ctx.guild.default_role,
            overwrite=overwrite,
            reason=f"{ctx.author} tarafından kilitlendi"
        )

        await ctx.send(
            "🔒 **Kanal kilitlendi.**"
        )


    # ========================================================
    # UNLOCK
    # ========================================================

    @bot.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    async def unlock_command(ctx):

        overwrite = ctx.channel.overwrites_for(
            ctx.guild.default_role
        )

        overwrite.send_messages = None

        await ctx.channel.set_permissions(
            ctx.guild.default_role,
            overwrite=overwrite,
            reason=f"{ctx.author} tarafından açıldı"
        )

        await ctx.send(
            "🔓 **Kanalın kilidi açıldı.**"
        )


    # ========================================================
    # SLOWMODE
    # ========================================================

    @bot.command(name="slowmode")
    @commands.has_permissions(manage_channels=True)
    async def slowmode_command(
        ctx,
        seconds: int = None
    ):

        if seconds is None:

            await ctx.send(
                "❌ Süre belirtmelisin.\n"
                "Örnek: `.slowmode 10`\n"
                "Kapatmak için: `.slowmode 0`"
            )
            return

        if seconds < 0:

            await ctx.send(
                "❌ Süre 0 veya daha yüksek olmalı."
            )
            return

        if seconds > 21600:

            await ctx.send(
                "❌ Slowmode en fazla 21600 saniye olabilir."
            )
            return

        try:

            await ctx.channel.edit(
                slowmode_delay=seconds,
                reason=f"{ctx.author} tarafından ayarlandı"
            )

            if seconds == 0:

                await ctx.send(
                    "🐌 **Slowmode kapatıldı.**"
                )

            else:

                await ctx.send(
                    f"🐌 **Slowmode {seconds} saniye olarak ayarlandı.**"
                )

        except discord.Forbidden:

            await ctx.send(
                "❌ Botun kanalı düzenleme yetkisi yok."
            )


    # ========================================================
    # SLASH BAN
    # ========================================================

    @bot.tree.command(
        name="ban",
        description="Bir kullanıcı için ban onayı iste."
    )
    @app_commands.describe(
        kullanici="Banlanmasını istediğin kullanıcı"
    )
    @app_commands.default_permissions(
        ban_members=True
    )
    async def slash_ban(
        interaction: discord.Interaction,
        kullanici: discord.Member
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        if kullanici.id == interaction.user.id:

            await interaction.followup.send(
                "❌ Kendini banlayamazsın.",
                ephemeral=True
            )
            return

        if kullanici.bot:

            await interaction.followup.send(
                "❌ Bot hesaplarını banlayamazsın.",
                ephemeral=True
            )
            return

        owner = bot_reference.get_user(
            OWNER_ID
        )

        if not owner:
            owner = await bot_reference.fetch_user(
                OWNER_ID
            )

        embed = discord.Embed(
            title="🚨 BAN ONAYI GEREKİYOR",
            description=(
                f"👤 **Banlanacak:** {kullanici.mention}\n"
                f"🆔 **ID:** `{kullanici.id}`\n\n"
                f"👮 **İsteği yapan:** "
                f"{interaction.user.mention}\n"
                f"🏠 **Sunucu:** "
                f"{interaction.guild.name}\n\n"
                "Banlamak için butona bas."
            ),
            color=discord.Color.red()
        )

        view = BanApprovalView(
            interaction.guild.id,
            kullanici.id,
            interaction.user.id
        )

        await owner.send(
            embed=embed,
            view=view
        )

        await interaction.followup.send(
            "📨 Ban isteği bot sahibine gönderildi.",
            ephemeral=True
        )


    # ========================================================
    # SLASH UNBAN
    # ========================================================

    @bot.tree.command(
        name="unban",
        description="ID ile unban onayı iste."
    )
    @app_commands.describe(
        kullanici_id="Banı kaldırılacak Discord kullanıcı ID'si"
    )
    @app_commands.default_permissions(
        ban_members=True
    )
    async def slash_unban(
        interaction: discord.Interaction,
        kullanici_id: str
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        try:

            target_id = int(kullanici_id)

        except ValueError:

            await interaction.followup.send(
                "❌ Geçerli bir Discord ID gir.",
                ephemeral=True
            )
            return

        try:

            target = await bot_reference.fetch_user(
                target_id
            )

        except discord.NotFound:

            await interaction.followup.send(
                "❌ Kullanıcı bulunamadı.",
                ephemeral=True
            )
            return

        owner = bot_reference.get_user(
            OWNER_ID
        )

        if not owner:

            owner = await bot_reference.fetch_user(
                OWNER_ID
            )

        embed = discord.Embed(
            title="🚨 UNBAN ONAYI GEREKİYOR",
            description=(
                f"👤 **Kullanıcı:** {target}\n"
                f"🆔 **ID:** `{target.id}`\n\n"
                f"👮 **İsteği yapan:** "
                f"{interaction.user.mention}\n"
                f"🏠 **Sunucu:** "
                f"{interaction.guild.name}\n\n"
                "Banı kaldırmak için butona bas."
            ),
            color=discord.Color.green()
        )

        embed.set_thumbnail(
            url=target.display_avatar.url
        )

        view = UnbanApprovalView(
            interaction.guild.id,
            target.id,
            interaction.user.id
        )

        await owner.send(
            embed=embed,
            view=view
        )

        await interaction.followup.send(
            "📨 Unban isteği bot sahibine gönderildi.",
            ephemeral=True
        )