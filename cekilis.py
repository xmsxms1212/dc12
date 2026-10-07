import asyncio
import random
import re
import time

import discord
from discord.ext import commands

OWNER_ID = 449133974867017728
bot_reference = None
giveaways = {}


def parse_duration(text):
    matches = re.findall(r"(\d+)\s*(s|m|h|d)", text.lower())
    if not matches:
        return None
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return sum(int(amount) * multipliers[unit] for amount, unit in matches)


def format_duration(seconds):
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f"{days}g")
    if hours:
        parts.append(f"{hours}s")
    if minutes:
        parts.append(f"{minutes}d")
    if seconds:
        parts.append(f"{seconds}sn")
    return " ".join(parts) or "0sn"


def weighted_winners(participants, weights, count):
    pool = list(participants)
    winners = []

    for _ in range(min(count, len(pool))):
        total = sum(weights.get(uid, 1) for uid in pool)
        pick = random.uniform(0, total)
        current = 0

        for uid in pool:
            current += weights.get(uid, 1)
            if pick <= current:
                winners.append(uid)
                pool.remove(uid)
                break

    return winners


async def update_giveaway_message(giveaway):
    try:
        channel = bot_reference.get_channel(giveaway["channel_id"])
        if channel is None:
            return

        message = await channel.fetch_message(giveaway["message_id"])

        embed = discord.Embed(
            title="🎉 ÇEKİLİŞ!",
            description=giveaway["description"],
            color=discord.Color.blurple()
        )

        if giveaway.get("image_url"):
            embed.set_image(url=giveaway["image_url"])

        embed.add_field(
            name="👥 Katılımcı",
            value=str(len(giveaway["participants"])),
            inline=True
        )
        embed.add_field(
            name="⏳ Bitiş",
            value=f"<t:{int(giveaway['end_time'])}:R>",
            inline=True
        )
        embed.set_footer(text=f"Çekiliş ID: {giveaway['id']}")

        await message.edit(
            embed=embed,
            view=GiveawayView(giveaway["id"])
        )

    except (discord.NotFound, discord.HTTPException):
        pass


class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

    @discord.ui.button(
        label="Katıl",
        emoji="🎉",
        style=discord.ButtonStyle.success,
        custom_id="giveaway_join"
    )
    async def join(self, interaction: discord.Interaction, button):
        giveaway = giveaways.get(self.giveaway_id)

        if giveaway is None or giveaway["ended"]:
            return await interaction.response.send_message(
                "❌ Bu çekiliş sona erdi.",
                ephemeral=True
            )

        uid = interaction.user.id

        if uid in giveaway["participants"]:
            giveaway["participants"].remove(uid)
            giveaway["weights"].pop(uid, None)

            await update_giveaway_message(giveaway)

            return await interaction.response.send_message(
                "❌ Çekilişten çıktın.",
                ephemeral=True
            )

        weight = 1
        role_id = giveaway.get("bonus_role_id")

        if role_id and isinstance(interaction.user, discord.Member):
            if any(role.id == role_id for role in interaction.user.roles):
                weight = giveaway["bonus_multiplier"]

        giveaway["participants"].add(uid)
        giveaway["weights"][uid] = weight

        await update_giveaway_message(giveaway)

        msg = (
            f"🎉 Katıldın! Şansın **{weight}x**."
            if weight > 1
            else "🎉 Çekilişe katıldın!"
        )

        await interaction.response.send_message(msg, ephemeral=True)


async def finish_giveaway(giveaway_id):
    giveaway = giveaways.get(giveaway_id)

    if giveaway is None:
        return

    remaining = giveaway["end_time"] - time.time()

    if remaining > 0:
        await asyncio.sleep(remaining)

    giveaway = giveaways.get(giveaway_id)

    if giveaway is None or giveaway["ended"]:
        return

    giveaway["ended"] = True

    channel = bot_reference.get_channel(giveaway["channel_id"])

    if channel is None:
        return

    participants = list(giveaway["participants"])
    winner_count = min(giveaway["winner_count"], len(participants))

    if winner_count == 0:
        embed = discord.Embed(
            title="🎉 Çekiliş Sona Erdi",
            description=(
                f"🎁 **Ödül:** {giveaway['prize']}\n\n"
                "😔 Katılımcı olmadığı için kazanan çıkmadı."
            ),
            color=discord.Color.red()
        )

        if giveaway.get("image_url"):
            embed.set_image(url=giveaway["image_url"])

        return await channel.send(embed=embed)

    winners = weighted_winners(
        participants,
        giveaway["weights"],
        winner_count
    )

    mentions = " ".join(f"<@{uid}>" for uid in winners)
    names = ", ".join(f"<@{uid}>" for uid in winners)

    embed = discord.Embed(
        title="🎉 ÇEKİLİŞ BİTTİ!",
        description=(
            f"🎁 **Ödül:** {giveaway['prize']}\n\n"
            f"🏆 **Kazanan:** {names}\n\n"
            f"👥 Katılımcı: **{len(participants)}**"
        ),
        color=discord.Color.gold()
    )

    if giveaway.get("image_url"):
        embed.set_image(url=giveaway["image_url"])

    await channel.send(
        content=f"🎉 Tebrikler {mentions}!",
        embed=embed
    )


class GiveawayConfig:
    def __init__(self):
        self.prize = None
        self.duration = None
        self.winner_count = None
        self.bonus_role_id = None
        self.bonus_multiplier = 1
        self.image_url = None


class GiveawayModal(discord.ui.Modal, title="🎉 Çekiliş Bilgileri"):
    prize = discord.ui.TextInput(
        label="Ödül",
        placeholder="Örn: Discord Nitro",
        max_length=200
    )

    duration = discord.ui.TextInput(
        label="Süre",
        placeholder="Örn: 30m, 2h, 1d",
        max_length=30
    )

    winners = discord.ui.TextInput(
        label="Kazanan sayısı",
        placeholder="Örn: 1",
        max_length=3
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            winner_count = int(self.winners.value)
        except ValueError:
            return await interaction.response.send_message(
                "❌ Kazanan sayısı sayı olmalı.",
                ephemeral=True
            )

        duration = parse_duration(self.duration.value)

        if duration is None:
            return await interaction.response.send_message(
                "❌ Geçersiz süre. Örnek: `30s`, `10m`, `2h`, `1d`",
                ephemeral=True
            )

        if duration < 10:
            return await interaction.response.send_message(
                "❌ Çekiliş en az 10 saniye olmalı.",
                ephemeral=True
            )

        if duration > 30 * 86400:
            return await interaction.response.send_message(
                "❌ Çekiliş en fazla 30 gün olabilir.",
                ephemeral=True
            )

        if winner_count < 1:
            return await interaction.response.send_message(
                "❌ En az 1 kazanan olmalı.",
                ephemeral=True
            )

        config = GiveawayConfig()
        config.prize = self.prize.value
        config.duration = duration
        config.winner_count = winner_count

        await interaction.response.send_message(
            "⭐ Aşağıdaki **rol menüsünden** bonus rolü seç.",
            view=GiveawayOptionsView(config),
            ephemeral=True
        )


class GiveawayOptionsView(discord.ui.View):
    def __init__(self, config):
        super().__init__(timeout=180)
        self.config = config
        self.add_item(RoleSelect(config))

    @discord.ui.button(
        label="⏭️ Bonus rol kullanma",
        style=discord.ButtonStyle.secondary,
        row=1
    )
    async def no_role(self, interaction: discord.Interaction, button):
        self.config.bonus_role_id = None
        self.config.bonus_multiplier = 1
        await interaction.response.send_modal(
            BonusChanceModal(self.config)
        )


class RoleSelect(discord.ui.RoleSelect):
    def __init__(self, config):
        super().__init__(
            placeholder="⭐ Bonus rolü buradan seç",
            min_values=1,
            max_values=1,
            row=0
        )
        self.config = config

    async def callback(self, interaction: discord.Interaction):
        role = self.values[0]
        self.config.bonus_role_id = role.id

        await interaction.response.send_modal(
            BonusChanceModal(self.config)
        )


class BonusChanceModal(discord.ui.Modal, title="⭐ Bonus Şans"):
    multiplier = discord.ui.TextInput(
        label="Bonus şans çarpanı",
        placeholder="Örn: 2 = 2x şans",
        max_length=3
    )

    def __init__(self, config):
        super().__init__()
        self.config = config

    async def on_submit(self, interaction):
        try:
            value = max(1, min(int(self.multiplier.value), 100))
        except ValueError:
            return await interaction.response.send_message(
                "❌ Şans sayısal olmalı. Örnek: `3`",
                ephemeral=True
            )

        self.config.bonus_multiplier = value

        await interaction.response.send_message(
            "🖼️ Son adım: Görsel eklemek için aşağıdaki butona bas.",
            view=ImageChoiceView(self.config),
            ephemeral=True
        )


class BonusChanceView(discord.ui.View):
    def __init__(self, config):
        super().__init__(timeout=180)
        self.config = config

    @discord.ui.button(
        label="⭐ Bonus Şansını Gir",
        style=discord.ButtonStyle.primary
    )
    async def bonus(self, interaction, button):
        await interaction.response.send_modal(
            BonusChanceModal(self.config)
        )


class ImageChoiceView(discord.ui.View):
    def __init__(self, config):
        super().__init__(timeout=180)
        self.config = config

    @discord.ui.button(
        label="🖼️ Görsel Seç",
        style=discord.ButtonStyle.primary
    )
    async def image(self, interaction, button):
        await interaction.response.send_message(
            "📎 Görseli **bu mesaja dosya olarak ekleyip gönder**.\n"
            "Discord botları butona basıldığında bilgisayarındaki dosya "
            "seçiciyi doğrudan açamaz. Dosyayı mesaj olarak yüklediğinde "
            "çekilişe otomatik ekleyebilirim.",
            ephemeral=True
        )

        def check(message):
            return (
                message.author.id == interaction.user.id
                and message.channel.id == interaction.channel.id
                and message.attachments
            )

        try:
            message = await bot_reference.wait_for(
                "message",
                timeout=120,
                check=check
            )
        except asyncio.TimeoutError:
            return await interaction.followup.send(
                "⏰ Görsel yükleme süresi doldu.",
                ephemeral=True
            )

        attachment = message.attachments[0]

        if not (
            (attachment.content_type and attachment.content_type.startswith("image/"))
            or attachment.filename.lower().endswith(
                (".png", ".jpg", ".jpeg", ".gif", ".webp")
            )
        ):
            return await interaction.followup.send(
                "❌ Bu dosya bir görsel değil.",
                ephemeral=True
            )

        self.config.image_url = attachment.url

        await interaction.followup.send(
            "✅ Görsel eklendi!",
            view=StartGiveawayView(self.config),
            ephemeral=True
        )


class StartGiveawayView(discord.ui.View):
    def __init__(self, config):
        super().__init__(timeout=180)
        self.config = config

    @discord.ui.button(
        label="🚀 Çekilişi Başlat",
        style=discord.ButtonStyle.success
    )
    async def start(self, interaction, button):
        await create_giveaway(interaction, self.config)


async def create_giveaway(interaction, config):
    end_time = time.time() + config.duration
    giveaway_id = int(time.time() * 1000)

    bonus_text = ""

    if config.bonus_role_id:
        role = interaction.guild.get_role(config.bonus_role_id)
        if role:
            bonus_text = (
                f"\n⭐ **Bonus şans:** {role.mention} üyeleri "
                f"**{config.bonus_multiplier}x** şansa sahip!"
            )

    description = (
        f"🎁 **Ödül:** {config.prize}\n\n"
        f"🏆 **Kazanan sayısı:** {config.winner_count}\n"
        f"⏰ **Süre:** {format_duration(config.duration)}"
        f"{bonus_text}\n\n"
        "Katılmak için aşağıdaki **🎉 Katıl** butonuna bas!"
    )

    giveaway = {
        "id": giveaway_id,
        "channel_id": interaction.channel.id,
        "guild_id": interaction.guild.id,
        "prize": config.prize,
        "winner_count": config.winner_count,
        "participants": set(),
        "weights": {},
        "end_time": end_time,
        "ended": False,
        "image_url": config.image_url,
        "bonus_role_id": config.bonus_role_id,
        "bonus_multiplier": config.bonus_multiplier,
        "description": description
    }

    giveaways[giveaway_id] = giveaway

    embed = discord.Embed(
        title="🎉 ÇEKİLİŞ!",
        description=description,
        color=discord.Color.blurple()
    )

    if config.image_url:
        embed.set_image(url=config.image_url)

    embed.add_field(name="👥 Katılımcı", value="0", inline=True)
    embed.add_field(
        name="⏳ Bitiş",
        value=f"<t:{int(end_time)}:R>",
        inline=True
    )
    embed.set_footer(text=f"Çekiliş ID: {giveaway_id}")

    message = await interaction.channel.send(
        embed=embed,
        view=GiveawayView(giveaway_id)
    )

    giveaway["message_id"] = message.id

    await interaction.response.edit_message(
        content="✅ Çekiliş başarıyla başlatıldı!",
        view=None
    )

    asyncio.create_task(finish_giveaway(giveaway_id))


def setup(bot):
    global bot_reference
    bot_reference = bot

    @bot.command(name="cekilis")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def cekilis(ctx):
        embed = discord.Embed(
            title="🎉 ÇEKİLİŞ SİSTEMİ",
            description=(
                "Aşağıdaki butona basarak çekiliş oluştur.\n\n"
                "🎁 Ödülünü gir\n"
                "⏱️ Süreyi gir\n"
                "🏆 Kazanan sayısını gir\n"
                "⭐ Rolü menüden seç\n"
                "🎯 Bonus şansını gir\n"
                "🖼️ Bilgisayarından görsel yükle"
            ),
            color=discord.Color.blurple()
        )

        await ctx.send(
            embed=embed,
            view=MainGiveawayView()
        )

    @cekilis.error
    async def cekilis_error(ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                "❌ Çekiliş menüsünü açmak için Yönetici yetkisi gerekli.",
                delete_after=5
            )


class MainGiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(
        label="🎉 Çekiliş Oluştur",
        style=discord.ButtonStyle.primary
    )
    async def create(self, interaction, button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Yönetici yetkisi gerekli.",
                ephemeral=True
            )

        await interaction.response.send_modal(GiveawayModal())