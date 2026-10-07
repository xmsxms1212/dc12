import discord
from discord.ext import commands


# ==========================================================
# BOT SAHİBİ
# ==========================================================

OWNER_ID = 449133974867017728


# ==========================================================
# BOT REFERANSI
# ==========================================================

bot_reference = None


# ==========================================================
# AKTİF TICKETLAR
# ==========================================================

# {
#     user_id: {
#         "username": "...",
#         "opened_at": ...
#     }
# }

tickets = {}


# ==========================================================
# TICKET NUMARASI
# ==========================================================

ticket_counter = 0


# ==========================================================
# KULLANICIYA DESTEK TALEBİ AÇTIRAN BUTON
# ==========================================================

class SupportStartView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )


    @discord.ui.button(
        label="Destek Talebi Aç",
        emoji="🎫",
        style=discord.ButtonStyle.primary
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        user_id = interaction.user.id

        # --------------------------------------------------
        # ZATEN TICKET VAR MI?
        # --------------------------------------------------

        if user_id in tickets:

            await interaction.response.send_message(
                "⚠️ Zaten açık bir destek talebin var.",
                ephemeral=True
            )

            return


        # --------------------------------------------------
        # MODAL AÇ
        # --------------------------------------------------

        await interaction.response.send_modal(
            SupportModal()
        )


# ==========================================================
# DESTEK MESAJI MODALI
# ==========================================================

class SupportModal(
    discord.ui.Modal,
    title="🎫 Destek Talebi"
):

    konu = discord.ui.TextInput(
        label="Sorunun nedir?",
        placeholder="Sorununu detaylı şekilde yaz...",
        style=discord.TextStyle.paragraph,
        required=True,
        min_length=5,
        max_length=2000
    )


    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        global ticket_counter

        user = interaction.user


        # --------------------------------------------------
        # ZATEN TICKET VAR MI?
        # --------------------------------------------------

        if user.id in tickets:

            await interaction.response.send_message(
                "⚠️ Zaten açık bir destek talebin var.",
                ephemeral=True
            )

            return


        ticket_counter += 1

        ticket_id = ticket_counter


        # --------------------------------------------------
        # TICKET KAYDET
        # --------------------------------------------------

        tickets[user.id] = {
            "ticket_id": ticket_id,
            "username": str(user),
            "user_id": user.id
        }


        # --------------------------------------------------
        # KULLANICIYA CEVAP
        # --------------------------------------------------

        await interaction.response.send_message(
            "✅ **Destek talebin oluşturuldu.**\n\n"
            "📨 Mesajın yetkiliye gönderildi.\n"
            "⏳ En kısa sürede sana cevap verilecek.",
        )


        # --------------------------------------------------
        # SAHİBİ BUL
        # --------------------------------------------------

        owner = bot_reference.get_user(
            OWNER_ID
        )

        if not owner:

            try:

                owner = await bot_reference.fetch_user(
                    OWNER_ID
                )

            except Exception:

                await user.send(
                    "❌ Destek sistemi sahibine ulaşamadı."
                )

                tickets.pop(
                    user.id,
                    None
                )

                return


        # --------------------------------------------------
        # SAHİBE DM
        # --------------------------------------------------

        embed = discord.Embed(
            title="🎫 YENİ DESTEK TALEBİ",
            description=(
                f"👤 **Kullanıcı:** {user}\n"
                f"🆔 **ID:** `{user.id}`\n"
                f"🎫 **Ticket:** `#{ticket_id}`\n\n"
                f"💬 **Mesaj:**\n"
                f"{self.konu.value}"
            ),
            color=discord.Color.blurple()
        )

        embed.set_thumbnail(
            url=user.display_avatar.url
        )

        embed.set_footer(
            text="PwoxAI Destek Sistemi"
        )


        await owner.send(
            embed=embed,
            view=OwnerTicketView(
                user.id,
                ticket_id
            )
        )


# ==========================================================
# SAHİBİN CEVAP VERMESİ İÇİN MODAL
# ==========================================================

class ReplyModal(
    discord.ui.Modal
):

    def __init__(
        self,
        user_id
    ):

        super().__init__(
            title="💬 Kullanıcıya Cevap Ver"
        )

        self.user_id = user_id


        self.message = discord.ui.TextInput(
            label="Cevabın",
            placeholder="Kullanıcıya göndermek istediğin mesaj...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000
        )


        self.add_item(
            self.message
        )


    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        # --------------------------------------------------
        # TICKET KONTROL
        # --------------------------------------------------

        ticket = tickets.get(
            self.user_id
        )

        if not ticket:

            await interaction.response.send_message(
                "❌ Bu ticket artık açık değil.",
                ephemeral=True
            )

            return


        # --------------------------------------------------
        # KULLANICIYI BUL
        # --------------------------------------------------

        try:

            user = await bot_reference.fetch_user(
                self.user_id
            )

        except Exception:

            await interaction.response.send_message(
                "❌ Kullanıcı bulunamadı.",
                ephemeral=True
            )

            return


        # --------------------------------------------------
        # KULLANICIYA MESAJ
        # --------------------------------------------------

        embed = discord.Embed(
            title="💬 DESTEK YETKİLİSİ",
            description=self.message.value,
            color=discord.Color.green()
        )

        embed.set_footer(
            text=f"Ticket #{ticket['ticket_id']}"
        )


        try:

            await user.send(
                embed=embed
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ Kullanıcıya DM gönderilemiyor.",
                ephemeral=True
            )

            return


        # --------------------------------------------------
        # SAHİBE BİLGİ
        # --------------------------------------------------

        await interaction.response.send_message(
            "✅ Cevabın kullanıcıya gönderildi.",
            ephemeral=True
        )


# ==========================================================
# TICKET KAPATMA ONAYI
# ==========================================================

class CloseConfirmView(
    discord.ui.View
):

    def __init__(
        self,
        user_id,
        ticket_id
    ):

        super().__init__(
            timeout=60
        )

        self.user_id = user_id
        self.ticket_id = ticket_id


    @discord.ui.button(
        label="Evet, Kapat",
        emoji="🔒",
        style=discord.ButtonStyle.danger
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user.id != OWNER_ID:

            await interaction.response.send_message(
                "❌ Bu işlemi sadece bot sahibi yapabilir.",
                ephemeral=True
            )

            return


        if self.user_id not in tickets:

            await interaction.response.edit_message(
                content="❌ Bu ticket zaten kapatılmış.",
                view=None
            )

            return


        # --------------------------------------------------
        # TICKET KAPAT
        # --------------------------------------------------

        tickets.pop(
            self.user_id,
            None
        )


        # --------------------------------------------------
        # KULLANICIYA PUANLAMA
        # --------------------------------------------------

        try:

            user = await bot_reference.fetch_user(
                self.user_id
            )

            await user.send(
                "🔒 **Destek talebin kapatıldı.**\n\n"
                "⭐ Aldığın destek hizmetini puanlar mısın?\n"
                "Aşağıdaki puanlardan birine bas.",
                view=RatingView(
                    self.ticket_id
                )
            )

        except discord.Forbidden:

            pass


        await interaction.response.edit_message(
            content=(
                f"🔒 **Ticket #{self.ticket_id} kapatıldı.**\n\n"
                "⭐ Kullanıcıya puanlama gönderildi."
            ),
            view=None
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

        if interaction.user.id != OWNER_ID:

            await interaction.response.send_message(
                "❌ Bu işlemi sadece bot sahibi yapabilir.",
                ephemeral=True
            )

            return


        await interaction.response.edit_message(
            content="↩️ Ticket kapatma işlemi iptal edildi.",
            view=None
        )


# ==========================================================
# SAHİP TICKET PANELİ
# ==========================================================

class OwnerTicketView(
    discord.ui.View
):

    def __init__(
        self,
        user_id,
        ticket_id
    ):

        super().__init__(
            timeout=None
        )

        self.user_id = user_id
        self.ticket_id = ticket_id


    # ======================================================
    # CEVAPLA
    # ======================================================

    @discord.ui.button(
        label="Cevapla",
        emoji="💬",
        style=discord.ButtonStyle.primary
    )
    async def reply(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user.id != OWNER_ID:

            await interaction.response.send_message(
                "❌ Bu butonu sadece bot sahibi kullanabilir.",
                ephemeral=True
            )

            return


        if self.user_id not in tickets:

            await interaction.response.send_message(
                "❌ Bu ticket artık açık değil.",
                ephemeral=True
            )

            return


        await interaction.response.send_modal(
            ReplyModal(
                self.user_id
            )
        )


    # ======================================================
    # KAPAT
    # ======================================================

    @discord.ui.button(
        label="Ticket Kapat",
        emoji="🔒",
        style=discord.ButtonStyle.danger
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user.id != OWNER_ID:

            await interaction.response.send_message(
                "❌ Bu butonu sadece bot sahibi kullanabilir.",
                ephemeral=True
            )

            return


        if self.user_id not in tickets:

            await interaction.response.send_message(
                "❌ Bu ticket zaten kapalı.",
                ephemeral=True
            )

            return


        await interaction.response.send_message(
            f"🔒 **Ticket #{self.ticket_id} kapatılsın mı?**",
            view=CloseConfirmView(
                self.user_id,
                self.ticket_id
            ),
            ephemeral=True
        )


# ==========================================================
# PUANLAMA
# ==========================================================

class RatingView(
    discord.ui.View
):

    def __init__(
        self,
        ticket_id
    ):

        super().__init__(
            timeout=300
        )

        self.ticket_id = ticket_id


    # ======================================================
    # PUAN BUTONLARI
    # ======================================================

    @discord.ui.button(
        label="1",
        emoji="⭐",
        style=discord.ButtonStyle.danger
    )
    async def one(
        self,
        interaction,
        button
    ):

        await interaction.response.send_modal(
            RatingModal(
                self.ticket_id,
                1
            )
        )


    @discord.ui.button(
        label="2",
        emoji="⭐",
        style=discord.ButtonStyle.danger
    )
    async def two(
        self,
        interaction,
        button
    ):

        await interaction.response.send_modal(
            RatingModal(
                self.ticket_id,
                2
            )
        )


    @discord.ui.button(
        label="3",
        emoji="⭐",
        style=discord.ButtonStyle.secondary
    )
    async def three(
        self,
        interaction,
        button
    ):

        await interaction.response.send_modal(
            RatingModal(
                self.ticket_id,
                3
            )
        )


    @discord.ui.button(
        label="4",
        emoji="⭐",
        style=discord.ButtonStyle.success
    )
    async def four(
        self,
        interaction,
        button
    ):

        await interaction.response.send_modal(
            RatingModal(
                self.ticket_id,
                4
            )
        )


    @discord.ui.button(
        label="5",
        emoji="⭐",
        style=discord.ButtonStyle.success
    )
    async def five(
        self,
        interaction,
        button
    ):

        await interaction.response.send_modal(
            RatingModal(
                self.ticket_id,
                5
            )
        )


# ==========================================================
# PUAN + NEDEN MODALI
# ==========================================================

class RatingModal(
    discord.ui.Modal
):

    def __init__(
        self,
        ticket_id,
        rating
    ):

        super().__init__(
            title=f"⭐ {rating}/5 Puan"
        )

        self.ticket_id = ticket_id
        self.rating = rating


        self.reason = discord.ui.TextInput(
            label="Neden bu puanı verdin?",
            placeholder="Kısaca nedenini yaz...",
            style=discord.TextStyle.paragraph,
            required=True,
            min_length=2,
            max_length=1000
        )


        self.add_item(
            self.reason
        )


    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        # --------------------------------------------------
        # KULLANICIYA CEVAP
        # --------------------------------------------------

        await interaction.response.send_message(
            f"✅ **{self.rating}/5** puanın ve yorumun "
            "yetkiliye gönderildi.\n"
            "Teşekkürler! ❤️"
        )


        # --------------------------------------------------
        # OWNER
        # --------------------------------------------------

        owner = bot_reference.get_user(
            OWNER_ID
        )

        if not owner:

            try:

                owner = await bot_reference.fetch_user(
                    OWNER_ID
                )

            except Exception:

                return


        # --------------------------------------------------
        # PUAN EMBED
        # --------------------------------------------------

        stars = "⭐" * self.rating


        embed = discord.Embed(
            title="📊 YENİ DESTEK PUANLAMASI",
            description=(
                f"🎫 **Ticket:** `#{self.ticket_id}`\n\n"
                f"👤 **Kullanıcı:** "
                f"{interaction.user}\n"
                f"🆔 **ID:** `{interaction.user.id}`\n\n"
                f"⭐ **Puan:** {self.rating}/5\n"
                f"{stars}\n\n"
                f"💬 **Sebep:**\n"
                f"{self.reason.value}"
            ),
            color=discord.Color.gold()
        )


        embed.set_thumbnail(
            url=interaction.user.display_avatar.url
        )


        embed.set_footer(
            text="PwoxAI • Destek Puanlama Sistemi"
        )


        await owner.send(
            embed=embed
        )


# ==========================================================
# NORMAL DM MESAJLARI
# ==========================================================

async def handle_dm(
    message
):

    if message.author.bot:
        return


    # ------------------------------------------------------
    # DM DEĞİLSE ÇIK
    # ------------------------------------------------------

    if message.guild is not None:
        return


    content = message.content.strip().lower()


    # ------------------------------------------------------
    # DESTEK KOMUTU
    # ------------------------------------------------------

    if content in (
        "destek",
        ".destek",
        "!destek"
    ):

        if message.author.id in tickets:

            await message.author.send(
                "⚠️ Zaten açık bir destek talebin var."
            )

            return


        await message.author.send(
            "🎫 **PwoxAI Destek Sistemi**\n\n"
            "Destek ekibine ulaşmak için "
            "aşağıdaki butona bas.",
            view=SupportStartView()
        )

        return


    # ------------------------------------------------------
    # AÇIK TICKET VARSA MESAJI SAHİBE GÖNDER
    # ------------------------------------------------------

    ticket = tickets.get(
        message.author.id
    )

    if not ticket:
        return


    owner = bot_reference.get_user(
        OWNER_ID
    )


    if not owner:

        try:

            owner = await bot_reference.fetch_user(
                OWNER_ID
            )

        except Exception:

            return


    embed = discord.Embed(
        title="💬 TICKET MESAJI",
        description=message.content,
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="👤 Kullanıcı",
        value=str(message.author),
        inline=True
    )

    embed.add_field(
        name="🆔 ID",
        value=str(message.author.id),
        inline=True
    )

    embed.add_field(
        name="🎫 Ticket",
        value=f"#{ticket['ticket_id']}",
        inline=True
    )


    # ------------------------------------------------------
    # EK DOSYA VARSA
    # ------------------------------------------------------

    if message.attachments:

        dosyalar = []

        for attachment in message.attachments:

            dosyalar.append(
                attachment.url
            )

        embed.add_field(
            name="📎 Dosyalar",
            value="\n".join(dosyalar)[:1024],
            inline=False
        )


    await owner.send(
        embed=embed,
        view=OwnerTicketView(
            message.author.id,
            ticket["ticket_id"]
        )
    )


# ==========================================================
# SETUP
# ==========================================================

def setup(
    bot
):

    global bot_reference

    bot_reference = bot


    # ------------------------------------------------------
    # DM MESSAGE EVENT
    # ------------------------------------------------------

    original_on_message = bot.on_message


    @bot.event
    async def on_message(
        message
    ):

        if message.author.bot:
            return


        # DM DESTEK SİSTEMİ
        if message.guild is None:

            await handle_dm(
                message
            )

            return


        # NORMAL KOMUTLAR
        await bot.process_commands(
            message
        )


    # ------------------------------------------------------
    # .destek
    # ------------------------------------------------------

    @bot.command(
        name="destek"
    )
    async def destek_command(
        ctx
    ):

        await ctx.send(
            "📩 **Destek sistemi DM üzerinden çalışıyor.**\n"
            "Bana DM'den `destek` yaz."
        )