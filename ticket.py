import discord
from discord.ext import commands
from discord import app_commands

# ==========================================
# AYARLAR
# ==========================================

OWNER_ID = 449133974867017728

# Ticketların açılacağı kategori.
# None bırakırsan bot otomatik olarak "🎫・TICKETS" kategorisi oluşturur.
TICKET_CATEGORY_ID = None

# Ticket yetkilileri:
# Owner + Administrator yetkisi olanlar ticketları yönetebilir.
# İstersen buraya rol ID'leri de ekleyebilirsin.
SUPPORT_ROLE_IDS = []

bot_reference = None


# Kullanıcı başına aynı anda 1 ticket
active_tickets = {}


# ==========================================
# YARDIMCI
# ==========================================

async def get_ticket_category(guild: discord.Guild):
    if TICKET_CATEGORY_ID:
        category = guild.get_channel(TICKET_CATEGORY_ID)
        if isinstance(category, discord.CategoryChannel):
            return category

    category = discord.utils.get(
        guild.categories,
        name="🎫・TICKETS"
    )

    if category:
        return category

    try:
        return await guild.create_category(
            "🎫・TICKETS",
            reason="Ticket sistemi kategori oluşturdu."
        )
    except discord.Forbidden:
        return None


def can_manage_ticket(member: discord.Member) -> bool:
    if member.id == OWNER_ID:
        return True

    if member.guild_permissions.administrator:
        return True

    return any(
        role.id in SUPPORT_ROLE_IDS
        for role in member.roles
    )


def ticket_channel_for(guild_id: int, user_id: int):
    return active_tickets.get((guild_id, user_id))


# ==========================================
# TICKET KAPATMA ONAYI
# ==========================================

class CloseConfirmView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=30)

    @discord.ui.button(
        label="Ticketı Kapat",
        emoji="🔒",
        style=discord.ButtonStyle.danger
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not isinstance(interaction.channel, discord.TextChannel):
            return await interaction.response.send_message(
                "❌ Bu buton ticket kanalında kullanılmalı.",
                ephemeral=True
            )

        if not can_manage_ticket(interaction.user):
            return await interaction.response.send_message(
                "❌ Bu ticketı kapatmak için yetkin yok.",
                ephemeral=True
            )

        channel = interaction.channel

        await interaction.response.send_message(
            "🔒 Ticket kapatılıyor..."
        )

        # Kayıttan çıkar
        for key, channel_id in list(active_tickets.items()):
            if channel_id == channel.id:
                active_tickets.pop(key, None)

        await channel.delete(
            reason=f"Ticket kapatıldı: {interaction.user}"
        )

    @discord.ui.button(
        label="İptal",
        emoji="↩️",
        style=discord.ButtonStyle.secondary
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content="❌ Ticket kapatma işlemi iptal edildi.",
            view=None
        )


class TicketControlView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Ticketı Kapat",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_close"
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not isinstance(interaction.channel, discord.TextChannel):
            return await interaction.response.send_message(
                "❌ Ticket kanalı bulunamadı.",
                ephemeral=True
            )

        if not can_manage_ticket(interaction.user):
            return await interaction.response.send_message(
                "❌ Bu ticketı kapatmak için yetkin yok.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "⚠️ Bu ticketı kapatmak istediğine emin misin?",
            view=CloseConfirmView(),
            ephemeral=True
        )


# ==========================================
# KATEGORİ SEÇİMİ
# ==========================================

class TicketTypeSelect(discord.ui.Select):

    def __init__(self):
        options = [
            discord.SelectOption(
                label="Genel Destek",
                description="Genel soru ve yardım",
                emoji="💬",
                value="genel"
            ),
            discord.SelectOption(
                label="Teknik Destek",
                description="Bot veya teknik sorunlar",
                emoji="🛠️",
                value="teknik"
            ),
            discord.SelectOption(
                label="Şikayet",
                description="Kullanıcı veya sunucu şikayeti",
                emoji="🚨",
                value="sikayet"
            ),
            discord.SelectOption(
                label="Diğer",
                description="Diğer konular",
                emoji="❓",
                value="diger"
            )
        ]

        super().__init__(
            placeholder="🎫 Ticket türünü seç...",
            options=options,
            custom_id="ticket_type_select"
        )

    async def callback(self, interaction: discord.Interaction):

        guild = interaction.guild
        user = interaction.user

        if guild is None:
            return await interaction.response.send_message(
                "❌ Bu sistem sadece sunucuda kullanılabilir.",
                ephemeral=True
            )

        key = (guild.id, user.id)

        existing_channel_id = active_tickets.get(key)

        if existing_channel_id:
            existing = guild.get_channel(existing_channel_id)

            if existing:
                return await interaction.response.send_message(
                    f"❌ Zaten açık bir ticketın var: {existing.mention}",
                    ephemeral=True
                )

            active_tickets.pop(key, None)

        category = await get_ticket_category(guild)

        if category is None:
            return await interaction.response.send_message(
                "❌ Ticket kategorisi oluşturulamadı.\n"
                "Botun `Kanal Yönet` ve `Kanal Oluştur` izinlerini kontrol et.",
                ephemeral=True
            )

        # Yetkileri oluştur
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            )
        }

        # Owner
        owner = guild.get_member(OWNER_ID)

        if owner:
            overwrites[owner] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True
            )

        # Destek rolleri
        for role_id in SUPPORT_ROLE_IDS:
            role = guild.get_role(role_id)

            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_messages=True
                )

        # Administrator üyeler
        # Discord'un administrator yetkisi zaten kanal izinlerini bypass eder.

        type_names = {
            "genel": "genel",
            "teknik": "teknik",
            "sikayet": "sikayet",
            "diger": "diger"
        }

        channel_name = (
            f"ticket-{type_names.get(self.values[0], 'ticket')}-"
            f"{user.name.lower().replace(' ', '-')[:20]}"
        )

        try:
            channel = await guild.create_text_channel(
                channel_name[:100],
                category=category,
                overwrites=overwrites,
                reason=f"Ticket açıldı: {user}"
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ Ticket kanalı oluşturulamadı.\n"
                "Botun `Kanal Yönet` / `Kanal Oluştur` izinlerini kontrol et.",
                ephemeral=True
            )
        except discord.HTTPException as e:
            return await interaction.response.send_message(
                f"❌ Discord hatası: `HTTP {e.status}`",
                ephemeral=True
            )

        active_tickets[key] = channel.id

        type_display = {
            "genel": "💬 Genel Destek",
            "teknik": "🛠️ Teknik Destek",
            "sikayet": "🚨 Şikayet",
            "diger": "❓ Diğer"
        }.get(self.values[0], "🎫 Ticket")

        embed = discord.Embed(
            title="🎫 Ticket Açıldı",
            description=(
                f"Hoş geldin {user.mention}!\n\n"
                "Sorununu veya talebini aşağıya yaz.\n"
                "Bir yetkili en kısa sürede ilgilenecektir.\n\n"
                f"**Ticket türü:** {type_display}"
            ),
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text="Ticketı kapatmak için aşağıdaki butonu kullan."
        )

        await interaction.response.send_message(
            f"✅ Ticketın oluşturuldu: {channel.mention}",
            ephemeral=True
        )

        await channel.send(
            content=f"{user.mention}",
            embed=embed,
            view=TicketControlView()
        )


class TicketPanelView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketTypeSelect())


# ==========================================
# TICKET PANEL KOMUTU
# ==========================================

def setup(bot):
    global bot_reference
    bot_reference = bot

    @bot.command(name="ticket")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def ticket(ctx):

        embed = discord.Embed(
            title="🎫 Destek Merkezi",
            description=(
                "Yardım almak veya bir sorun bildirmek için "
                "aşağıdaki menüden ticket türünü seç.\n\n"
                "🔹 **Genel Destek** — Genel sorular\n"
                "🔹 **Teknik Destek** — Bot/teknik sorunlar\n"
                "🔹 **Şikayet** — Şikayet ve bildirimler\n"
                "🔹 **Diğer** — Diğer konular\n\n"
                "⚠️ Aynı anda yalnızca **1 açık ticket** oluşturabilirsin."
            ),
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text="PwoxAI Ticket Sistemi"
        )

        await ctx.send(
            embed=embed,
            view=TicketPanelView()
        )

    @ticket.error
    async def ticket_error(ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                "❌ Ticket panelini sadece **Yönetici** yetkisi olanlar oluşturabilir.",
                delete_after=5
            )

    # Bot yeniden başlatıldığında panel butonlarının çalışması için.
    bot.add_view(TicketPanelView())
    bot.add_view(TicketControlView())
