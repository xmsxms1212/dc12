import asyncio
import time
import discord
import yt_dlp

from discord import app_commands


# ==========================================================
# SAHİP / DJ ID
# ==========================================================

OWNER_ID = 449133974867017728


# ==========================================================
# BOT REFERANSI
# ==========================================================

bot_reference = None


# ==========================================================
# KUYRUK
# ==========================================================

queues = {}
now_playing = {}


# ==========================================================
# SON ŞARKI / KALDIĞI YER
# ==========================================================

last_song = {}

# Şarkının kaldığı saniye
paused_position = {}

# Şarkının çalmaya başladığı zaman
play_started_at = {}

# Konum takip görevleri
position_tasks = {}


# ==========================================================
# MANUEL STOP KONTROLÜ
# ==========================================================

manual_stop = {}


# ==========================================================
# YOUTUBE ARAMA AYARLARI
# ==========================================================

SEARCH_OPTS = {
    "quiet": True,
    "noplaylist": True,
    "extract_flat": True,
}


AUDIO_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": True,
}


# ==========================================================
# YOUTUBE ARAMA
# ==========================================================

async def youtube_search(query, limit=5):

    def search():

        with yt_dlp.YoutubeDL(
            SEARCH_OPTS
        ) as ydl:

            info = ydl.extract_info(
                f"ytsearch{limit}:{query}",
                download=False
            )

            return info.get(
                "entries",
                []
            )

    return await asyncio.to_thread(
        search
    )


# ==========================================================
# SES LINKİ AL
# ==========================================================

async def get_audio(url):

    def extract():

        with yt_dlp.YoutubeDL(
            AUDIO_OPTS
        ) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

            return {
                "url": info["url"],

                "title": info.get(
                    "title",
                    "Bilinmeyen şarkı"
                ),

                "webpage_url": info.get(
                    "webpage_url",
                    url
                )
            }

    return await asyncio.to_thread(
        extract
    )


# ==========================================================
# SAHİP KONTROLÜ
# ==========================================================

def is_owner(user):

    return user.id == OWNER_ID


# ==========================================================
# MEVCUT KONUMU HESAPLA
# ==========================================================

def get_current_position(
    guild_id
):

    position = paused_position.get(
        guild_id,
        0
    )

    started = play_started_at.get(
        guild_id
    )

    if started is not None:

        position += (
            time.monotonic()
            - started
        )

    return max(
        0,
        position
    )


# ==========================================================
# KONUMU ARKA PLANDA TAKİP ET
# ==========================================================

async def track_position(
    guild_id
):

    while True:

        guild = bot_reference.get_guild(
            guild_id
        )

        if not guild:
            break

        voice = guild.voice_client

        if not voice:
            break

        if voice.is_playing():

            paused_position[
                guild_id
            ] = get_current_position(
                guild_id
            )

        await asyncio.sleep(
            0.5
        )


# ==========================================================
# KONUM TAKİP GÖREVİNİ BAŞLAT
# ==========================================================

def start_position_tracker(
    guild_id
):

    old_task = position_tasks.get(
        guild_id
    )

    if old_task and not old_task.done():

        return

    task = asyncio.create_task(
        track_position(
            guild_id
        )
    )

    position_tasks[
        guild_id
    ] = task


# ==========================================================
# FFmpeg SOURCE
# ==========================================================

def create_source(
    url,
    position=0
):

    before_options = (
        "-reconnect 1 "
        "-reconnect_streamed 1 "
        "-reconnect_delay_max 5"
    )

    if position > 0:

        before_options += (
            f" -ss {position:.2f}"
        )

    return discord.FFmpegPCMAudio(
        url,
        before_options=before_options,
        options="-vn"
    )


# ==========================================================
# ŞARKI BAŞLAT
# ==========================================================

async def start_song(
    guild_id,
    song,
    position=0
):

    guild = bot_reference.get_guild(
        guild_id
    )

    if not guild:
        return False

    voice = guild.voice_client

    if not voice:
        return False

    try:

        data = await get_audio(
            song["webpage_url"]
        )

        source = create_source(
            data["url"],
            position
        )

        now_playing[
            guild_id
        ] = data

        last_song[
            guild_id
        ] = {
            "title": data[
                "title"
            ],

            "webpage_url": data[
                "webpage_url"
            ]
        }

        paused_position[
            guild_id
        ] = position

        play_started_at[
            guild_id
        ] = time.monotonic()

        manual_stop[
            guild_id
        ] = False

        voice.play(
            source,

            after=lambda error:
                asyncio.run_coroutine_threadsafe(
                    play_next(
                        guild_id
                    ),
                    bot_reference.loop
                )
        )

        start_position_tracker(
            guild_id
        )

        return True

    except Exception as e:

        print(
            "[MÜZİK HATASI] "
            f"{type(e).__name__}: {e}"
        )

        return False


# ==========================================================
# SONRAKİ ŞARKI
# ==========================================================

async def play_next(
    guild_id
):

    if manual_stop.get(
        guild_id,
        False
    ):

        manual_stop[
            guild_id
        ] = False

        return

    queue = queues.get(
        guild_id,
        []
    )

    if not queue:

        now_playing.pop(
            guild_id,
            None
        )

        play_started_at.pop(
            guild_id,
            None
        )

        return

    guild = bot_reference.get_guild(
        guild_id
    )

    if not guild:
        return

    voice = guild.voice_client

    if not voice:
        return

    song = queue.pop(0)

    success = await start_song(
        guild_id,
        song,
        0
    )

    if not success:

        await play_next(
            guild_id
        )


# ==========================================================
# MÜZİK KONTROLLERİ
# ==========================================================

class MusicControls(
    discord.ui.View
):

    def __init__(
        self,
        bot,
        guild_id
    ):

        super().__init__(
            timeout=None
        )

        self.bot = bot
        self.guild_id = guild_id


    # ======================================================
    # SADECE SAHİP
    # ======================================================

    async def owner_only(
        self,
        interaction
    ):

        if not is_owner(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ Bu müzik panelini sadece bot sahibi kullanabilir.",
                ephemeral=True
            )

            return False

        return True


    # ======================================================
    # DURAKLAT
    # ======================================================

    @discord.ui.button(
        label="Duraklat",
        emoji="⏸️",
        style=discord.ButtonStyle.secondary
    )
    async def pause(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not await self.owner_only(
            interaction
        ):
            return

        voice = interaction.guild.voice_client

        if voice and voice.is_playing():

            paused_position[
                self.guild_id
            ] = get_current_position(
                self.guild_id
            )

            play_started_at.pop(
                self.guild_id,
                None
            )

            voice.pause()

            await interaction.response.send_message(
                "⏸️ Müzik duraklatıldı.\n"
                f"⏱️ Konum: **"
                f"{int(paused_position[self.guild_id])}"
                " saniye**",
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                "❌ Şu anda çalan şarkı yok.",
                ephemeral=True
            )


    # ======================================================
    # DEVAM
    # ======================================================

    @discord.ui.button(
        label="Devam",
        emoji="▶️",
        style=discord.ButtonStyle.success
    )
    async def resume(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not await self.owner_only(
            interaction
        ):
            return

        voice = interaction.guild.voice_client

        if voice and voice.is_paused():

            voice.resume()

            play_started_at[
                self.guild_id
            ] = time.monotonic()

            start_position_tracker(
                self.guild_id
            )

            await interaction.response.send_message(
                "▶️ Müzik devam ediyor.",
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                "❌ Müzik duraklatılmış değil.",
                ephemeral=True
            )


    # ======================================================
    # SONRAKİ
    # ======================================================

    @discord.ui.button(
        label="Sonraki",
        emoji="⏭️",
        style=discord.ButtonStyle.primary
    )
    async def skip(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not await self.owner_only(
            interaction
        ):
            return

        voice = interaction.guild.voice_client

        if voice and (
            voice.is_playing()
            or voice.is_paused()
        ):

            manual_stop[
                self.guild_id
            ] = False

            play_started_at.pop(
                self.guild_id,
                None
            )

            paused_position[
                self.guild_id
            ] = 0

            voice.stop()

            await interaction.response.send_message(
                "⏭️ Sonraki şarkıya geçiliyor.",
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                "❌ Şu anda çalan şarkı yok.",
                ephemeral=True
            )


    # ======================================================
    # DURDUR
    # ======================================================

    @discord.ui.button(
        label="Durdur",
        emoji="⏹️",
        style=discord.ButtonStyle.danger
    )
    async def stop(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not await self.owner_only(
            interaction
        ):
            return

        voice = interaction.guild.voice_client

        if voice and (
            voice.is_playing()
            or voice.is_paused()
        ):

            if voice.is_playing():

                paused_position[
                    self.guild_id
                ] = get_current_position(
                    self.guild_id
                )

            manual_stop[
                self.guild_id
            ] = True

            play_started_at.pop(
                self.guild_id,
                None
            )

        queues[
            self.guild_id
        ] = []

        now_playing.pop(
            self.guild_id,
            None
        )

        if voice:

            voice.stop()

            await interaction.response.send_message(
                "⏹️ Müzik durduruldu.\n"
                "▶️ Kaldığı yer kaydedildi.",
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                "❌ Bot ses kanalında değil.",
                ephemeral=True
            )


    # ======================================================
    # ŞARKI DEĞİŞTİR
    # ======================================================

    @discord.ui.button(
        label="Değiştir",
        emoji="🔄",
        style=discord.ButtonStyle.secondary
    )
    async def change(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not await self.owner_only(
            interaction
        ):
            return

        await interaction.response.send_modal(
            ChangeSongModal(
                self.guild_id
            )
        )


# ==========================================================
# ŞARKI DEĞİŞTİRME MODALI
# ==========================================================

class ChangeSongModal(
    discord.ui.Modal
):

    def __init__(
        self,
        guild_id
    ):

        super().__init__(
            title="Şarkıyı Değiştir"
        )

        self.guild_id = guild_id

        self.song = discord.ui.TextInput(
            label="Yeni şarkı",
            placeholder="Örn: Ezhel - Geceler",
            required=True,
            max_length=200
        )

        self.add_item(
            self.song
        )


    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        voice = interaction.guild.voice_client

        if not voice:

            await interaction.followup.send(
                "❌ Bot ses kanalında değil.",
                ephemeral=True
            )

            return

        try:

            results = await youtube_search(
                self.song.value,
                1
            )

            if not results:

                await interaction.followup.send(
                    "❌ Şarkı bulunamadı.",
                    ephemeral=True
                )

                return

            result = results[0]

            url = result.get(
                "url"
            )

            if not url:

                await interaction.followup.send(
                    "❌ YouTube sonucu alınamadı.",
                    ephemeral=True
                )

                return

            if not url.startswith(
                "http"
            ):

                url = (
                    "https://www.youtube.com/watch?v="
                    + url
                )

            song = {
                "title": result.get(
                    "title",
                    "Bilinmeyen şarkı"
                ),

                "webpage_url": url
            }

            queues[
                self.guild_id
            ] = []

            manual_stop[
                self.guild_id
            ] = True

            if (
                voice.is_playing()
                or voice.is_paused()
            ):

                voice.stop()

            await asyncio.sleep(
                0.2
            )

            manual_stop[
                self.guild_id
            ] = False

            paused_position[
                self.guild_id
            ] = 0

            play_started_at[
                self.guild_id
            ] = time.monotonic()

            success = await start_song(
                self.guild_id,
                song,
                0
            )

            if not success:

                await interaction.followup.send(
                    "❌ Şarkı başlatılamadı.",
                    ephemeral=True
                )

                return

            await interaction.followup.send(
                "🔄 Şarkı değiştirildi:\n"
                f"🎵 **{song['title']}**",
                ephemeral=True
            )

        except Exception as e:

            await interaction.followup.send(
                "❌ Hata: "
                f"`{type(e).__name__}: {e}`",
                ephemeral=True
            )


# ==========================================================
# ŞARKI SEÇME
# ==========================================================

class SongSelect(
    discord.ui.Select
):

    def __init__(
        self,
        results,
        guild_id
    ):

        self.results = results
        self.guild_id = guild_id

        options = []

        for i, result in enumerate(
            results
        ):

            title = result.get(
                "title",
                "Bilinmeyen şarkı"
            )

            options.append(
                discord.SelectOption(
                    label=title[:100],
                    value=str(i)
                )
            )

        super().__init__(
            placeholder=(
                "🎵 Çalmak istediğin "
                "şarkıyı seç..."
            ),

            options=options
        )


    async def callback(
        self,
        interaction: discord.Interaction
    ):

        await interaction.response.defer()

        index = int(
            self.values[0]
        )

        result = self.results[
            index
        ]

        url = result.get(
            "url"
        )

        if not url:

            await interaction.followup.send(
                "❌ Şarkı linki alınamadı."
            )

            return

        if not url.startswith(
            "http"
        ):

            url = (
                "https://www.youtube.com/watch?v="
                + url
            )

        song = {
            "title": result.get(
                "title",
                "Bilinmeyen şarkı"
            ),

            "webpage_url": url
        }

        guild = interaction.guild

        if not guild:

            await interaction.followup.send(
                "❌ Sunucu bulunamadı."
            )

            return

        if not interaction.user.voice:

            await interaction.followup.send(
                "❌ Önce bir ses kanalına gir."
            )

            return

        channel = (
            interaction.user.voice.channel
        )

        voice = guild.voice_client

        try:

            if not voice:

                voice = await channel.connect(
                    self_deaf=True
                )

            elif voice.channel != channel:

                await voice.move_to(
                    channel
                )

            guild_id = guild.id

            if guild_id not in queues:

                queues[
                    guild_id
                ] = []


            # ==================================================
            # ŞARKI ÇALIYORSA KUYRUĞA EKLE
            # ==================================================

            if (
                voice.is_playing()
                or voice.is_paused()
            ):

                queues[
                    guild_id
                ].append(song)

                sıra = len(
                    queues[guild_id]
                )

                await interaction.followup.send(
                    "➕ **Kuyruğa eklendi!**\n"
                    f"🎵 **{song['title']}**\n"
                    f"📌 Sıra: **{sıra}**"
                )

                return


            # ==================================================
            # ŞARKI ÇALMIYORSA BAŞLAT
            # ==================================================

            success = await start_song(
                guild_id,
                song,
                0
            )

            if not success:

                await interaction.followup.send(
                    "❌ Şarkı başlatılamadı."
                )

                return

            await interaction.followup.send(
                "🎵 **Şimdi çalıyor:**\n"
                f"**{now_playing[guild_id]['title']}**",

                view=MusicControls(
                    bot_reference,
                    guild_id
                )
            )

        except Exception as e:

            await interaction.followup.send(
                "❌ Hata: "
                f"`{type(e).__name__}: {e}`"
            )


# ==========================================================
# ŞARKI SEÇME VIEW
# ==========================================================

class SongSelectView(
    discord.ui.View
):

    def __init__(
        self,
        results,
        guild_id
    ):

        super().__init__(
            timeout=60
        )

        self.add_item(
            SongSelect(
                results,
                guild_id
            )
        )


# ==========================================================
# BOT SETUP
# ==========================================================

def setup(bot):

    global bot_reference

    bot_reference = bot


    # ======================================================
    # /cal
    # ======================================================

    @bot.tree.command(
        name="cal",
        description="YouTube'dan şarkı ara ve çal."
    )
    @app_commands.describe(
        sarki="Aramak istediğin şarkı"
    )
    async def cal(
        interaction: discord.Interaction,
        sarki: str
    ):

        await interaction.response.defer()

        try:

            results = await youtube_search(
                sarki,
                5
            )

            if not results:

                await interaction.followup.send(
                    "❌ Şarkı bulunamadı."
                )

                return

            await interaction.followup.send(
                "🎵 **Arama sonuçları:**\n"
                "Aşağıdan çalmak istediğin şarkıyı seç.",

                view=SongSelectView(
                    results,
                    interaction.guild.id
                )
            )

        except Exception as e:

            await interaction.followup.send(
                "❌ Arama hatası: "
                f"`{type(e).__name__}: {e}`"
            )


    # ======================================================
    # .calmayadevamet / !calmayadevamet
    # ======================================================

    @bot.command(
        name="calmayadevamet"
    )
    async def calmayadevamet(
        ctx
    ):

        guild = ctx.guild

        if not guild:

            await ctx.send(
                "❌ Bu komut sadece sunucuda kullanılabilir."
            )

            return

        guild_id = guild.id

        song = last_song.get(
            guild_id
        )

        if not song:

            await ctx.send(
                "❌ Devam ettirilecek son şarkı bulunamadı."
            )

            return

        if not ctx.author.voice:

            await ctx.send(
                "❌ Önce bir ses kanalına gir."
            )

            return

        channel = (
            ctx.author.voice.channel
        )

        voice = guild.voice_client

        try:

            # ==================================================
            # BOT SES KANALINDA DEĞİLSE GİR
            # ==================================================

            if not voice:

                voice = await channel.connect(
                    self_deaf=True
                )

            elif voice.channel != channel:

                await voice.move_to(
                    channel
                )


            # ==================================================
            # ŞU AN ÇALAN VARSA DURDUR
            # ==================================================

            if (
                voice.is_playing()
                or voice.is_paused()
            ):

                manual_stop[
                    guild_id
                ] = True

                voice.stop()

                await asyncio.sleep(
                    0.2
                )

                manual_stop[
                    guild_id
                ] = False


            # ==================================================
            # KALDIĞI YER
            # ==================================================

            position = paused_position.get(
                guild_id,
                0
            )

            position = max(
                0,
                position
            )


            # ==================================================
            # TEKRAR BAŞLAT
            # ==================================================

            success = await start_song(
                guild_id,
                song,
                position
            )

            if not success:

                await ctx.send(
                    "❌ Şarkı devam ettirilemedi."
                )

                return

            dakika = int(
                position // 60
            )

            saniye = int(
                position % 60
            )

            await ctx.send(
                "▶️ **Şarkı kaldığı yerden devam ediyor!**\n"
                f"🎵 **{song['title']}**\n"
                f"⏱️ **{dakika}:{saniye:02d}**"
            )

        except Exception as e:

            await ctx.send(
                "❌ Hata: "
                f"`{type(e).__name__}: {e}`"
            )