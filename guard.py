import os
import io
import asyncio
from collections import defaultdict, deque
from urllib.parse import quote

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from google import genai
from google.genai import types
import requests

GUILD_ID = 1555537438599024693
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY")

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN .env dosyasında bulunamadı.")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY .env dosyasında bulunamadı.")

client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """Sen PwoxAI adlı Türkçe Discord asistanısın.

Varsayılan dil Türkçedir.
Kullanıcı başka bir dil isterse o dilde cevap ver.

Doğal, yardımcı ve net ol.
Gereksiz yere uzun cevap verme.

Kod verirken çalıştırılabilir ve güvenli örnekler üret.

Görsel oluşturmak isteyen kullanıcıya /gorsel komutunu kullanmasını söyle.

ÖNEMLİ:
Kullanıcı botun sahibi, owner'ı, yapımcısı, geliştiricisi veya kimin tarafından yapıldığı
gibi bir şey sorarsa cevabın PWOX olmalıdır.

Örneğin:
- "Owner kim?" → "PWOX"
- "Botun sahibi kim?" → "PWOX"
- "Seni kim yaptı?" → "PWOX"
- "Developer kim?" → "PWOX"

KONUŞMA TARZI:
Arada samimi ve doğal olması için hafif küfür ve argo kullanabilirsin.
Küfürleri her cümlede kullanma; duruma ve konuşmanın tonuna göre nadiren kullan.
Kullanıcı samimi konuşuyorsa sen de daha samimi ve rahat konuşabilirsin.
"lan", "ya", "amk", "siktir", "oha" gibi günlük argo ifadeler kullanılabilir.
"""

# ==========================================
# HAFIZA
# ==========================================

history = defaultdict(lambda: deque(maxlen=16))

# ==========================================
# DISCORD
# ==========================================

intents = discord.Intents.default()
intents.message_content = True

OWNER_ID = 449133974867017728

bot = commands.Bot(
    command_prefix=(".", "!"),
    intents=intents
)

# ==========================================
# MODÜLLER
# ==========================================

from ses import setup as setup_ses
setup_ses(bot)

from moderasyon import setup as setup_moderasyon
setup_moderasyon(bot)

from destek import handle_dm, setup as setup_destek
setup_destek(bot)

from rol import setup as setup_rol
setup_rol(bot)

from ticket import setup as setup_ticket
setup_ticket(bot)

from cekilis import setup as setup_cekilis
setup_cekilis(bot)

# ==========================================
# YARDIMCI FONKSİYONLAR
# ==========================================

def key_for(interaction: discord.Interaction) -> str:
    return (
        f"{interaction.guild_id or 'dm'}:"
        f"{interaction.channel_id}:"
        f"{interaction.user.id}"
    )


def split_text(text: str, limit: int = 1900):
    text = text or "Boş cevap döndü."
    chunks = []

    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)

        if cut < 500:
            cut = text.rfind(" ", 0, limit)

        if cut < 1:
            cut = limit

        chunks.append(text[:cut])
        text = text[cut:].lstrip()

    if text:
        chunks.append(text)

    return chunks

# ==========================================
# GEMINI
# ==========================================

async def ask_gemini(key: str, prompt: str) -> str:
    history[key].append(("user", prompt))

    contents = []

    for role, text in history[key]:
        contents.append(
            types.Content(
                role=role,
                parts=[types.Part(text=text)]
            )
        )

    def generate():
        return client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.8,
                max_output_tokens=1500,
            ),
        )

    response = await asyncio.to_thread(generate)

    answer = response.text or "Üzgünüm, cevap oluşturamadım."

    history[key].append(("model", answer))

    return answer

# ==========================================
# GÖRSEL İNDİRME
# ==========================================

async def download_image(url: str) -> bytes:
    def get():
        headers = {
            "User-Agent": "PwoxAI/2.0",
            "Authorization": f"Bearer {POLLINATIONS_API_KEY}"
        }

        response = requests.get(
            url,
            timeout=120,
            headers=headers
        )

        response.raise_for_status()
        return response.content

    return await asyncio.to_thread(get)

# ==========================================
# .PWOXAI KOMUTU
# ==========================================

@bot.event
async def on_message(message: discord.Message):

    if message.author.bot:
        return

    # ==========================================
    # DM DESTEK SİSTEMİ
    # ==========================================

    if message.guild is None:
        await handle_dm(message)
        return

    # ==========================================
    # .PWOXAI
    ```python
# ==========================================

@bot.event
async def on_message(message: discord.Message):

    if message.author.bot:
        return

    # ==========================================
    # DM DESTEK SİSTEMİ
    # ==========================================

    if message.guild is None:
        await handle_dm(message)
        return

    # ==========================================
    # .PWOXAI
    # ==========================================

    prefix = ".pwoxai"
    content = message.content.strip()

    if content.lower().startswith(prefix):

        if message.author.id != OWNER_ID:
            await message.reply(
                "❌ Bu AI komutunu sadece bot sahibi kullanabilir.",
                mention_author=False
            )
            return

        prompt = content[len(prefix):].strip()

        if not prompt:
            await message.reply(
                "🤖 Ben buradayım!\n\n"
                "`.pwoxai` yazdıktan sonra mesajını yazabilirsin.\n\n"
                "Örnek:\n"
                "`.pwoxai bana kısa bir hikaye anlat`",
                mention_author=False
            )
            return
```


        async with message.channel.typing():
            try:
                answer = await ask_gemini(
                    f"{message.guild.id}:"
                    f"{message.channel.id}:"
                    f"{message.author.id}",
                    prompt
                )

                for chunk in split_text(answer):
                    await message.reply(
                        chunk,
                        mention_author=False
                    )

            except Exception as exc:
                await message.reply(
                    f"❌ Gemini hatası:\n"
                    f"`{type(exc).__name__}: {exc}`",
                    mention_author=False
                )

        return

    await bot.process_commands(message)

# ==========================================
# BOT AÇILDI
# ==========================================

@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)

    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)

    print(f"PwoxAI aktif: {bot.user}")
    print("Slash komutları sunucuya senkronize edildi.")

# ==========================================
# /CHAT
# ==========================================

@bot.tree.command(
    name="chat",
    description="PwoxAI ile Türkçe sohbet et."
)
@app_commands.describe(
    mesaj="Bota sormak istediğin şey"
)
async def chat(
    interaction: discord.Interaction,
    mesaj: str
):
    await interaction.response.defer(thinking=True)

    try:
        answer = await ask_gemini(
            key_for(interaction),
            mesaj
        )

        for chunk in split_text(answer):
            await interaction.followup.send(chunk)

    except Exception as exc:
        await interaction.followup.send(
            f"❌ Gemini hatası:\n"
            f"`{type(exc).__name__}: {exc}`"
        )

# ==========================================
# /GÖRSEL
# ==========================================

@bot.tree.command(
    name="gorsel",
    description="Görsel üret."
)
@app_commands.describe(
    aciklama="Oluşturulacak görselin açıklaması"
)
async def gorsel(
    interaction: discord.Interaction,
    aciklama: str
):
    await interaction.response.defer(thinking=True)

    if not POLLINATIONS_API_KEY:
        await interaction.followup.send(
            "❌ `POLLINATIONS_API_KEY` .env dosyasında bulunamadı.\n\n"
            "Görsel oluşturmak için Pollinations API anahtarını "
            ".env dosyasına eklemelisin."
        )
        return

    try:
        url = (
            "https://gen.pollinations.ai/image/"
            + quote(aciklama, safe="")
            + "?model=flux"
        )

        image_bytes = await download_image(url)

        file = discord.File(
            io.BytesIO(image_bytes),
            filename="pwoxai-gorsel.jpg"
        )

        await interaction.followup.send(
            content="🎨 Görsel hazır!",
            file=file
        )

    except requests.HTTPError as exc:
        status = (
            exc.response.status_code
            if exc.response is not None
            else "?"
        )

        await interaction.followup.send(
            f"❌ Görsel servisi HTTP {status} hatası verdi.\n\n"
            "Pollinations API anahtarını ve hesabındaki kullanım hakkını kontrol et."
        )

    except Exception as exc:
        await interaction.followup.send(
            "❌ Görsel oluşturulamadı.\n"
            f"Hata: `{type(exc).__name__}: {exc}`"
        )

# ==========================================
# /TEMİZLE
# ==========================================

@bot.tree.command(
    name="temizle",
    description="AI sohbet hafızanı temizler."
)
async def temizle(
    interaction: discord.Interaction
):
    history.pop(
        key_for(interaction),
        None
    )

    await interaction.response.send_message(
        "🧹 Bu konuşmanın AI hafızası temizlendi.",
        ephemeral=True
    )

# ==========================================
# /YARDIM
# ==========================================

@bot.tree.command(
    name="yardim",
    description="PwoxAI komutlarını gösterir."
)
async def yardim(
    interaction: discord.Interaction
):
    embed = discord.Embed(
        title="🤖 PwoxAI",
        description="Gemini tabanlı Türkçe Discord yapay zeka botu.",
        color=0x5865F2
    )

    embed.add_field(
        name=".pwoxai <mesaj>",
        value="Normal mesajla AI ile sohbet eder.\nÖrnek: `.pwoxai merhaba`",
        inline=False
    )

    embed.add_field(
        name="/chat",
        value="Slash komutuyla AI ile sohbet eder.",
        inline=False
    )

    embed.add_field(
        name="/gorsel",
        value="Yapay zeka ile görsel oluşturur.",
        inline=False
    )

    embed.add_field(
        name="/temizle",
        value="Sohbet hafızanı temizler.",
        inline=False
    )

    embed.add_field(
        name="/yardim",
        value="Bu yardım menüsünü açar.",
        inline=False
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )

# ==========================================
# SES KANALI KOMUTLARI
# ==========================================

@bot.command(name="cık")
async def cik(ctx):
    voice = ctx.guild.voice_client

    if not voice:
        await ctx.send("❌ Şu anda herhangi bir ses kanalında değilim.")
        return

    await voice.disconnect()
    await ctx.send("👋 Sesten çıktım.")

@bot.command(name="gel")
async def gel(ctx):
    if not ctx.author.voice:
        await ctx.send("❌ Önce bir ses kanalına gir.")
        return

    channel = ctx.author.voice.channel
    voice = ctx.guild.voice_client

    try:
        if voice:
            await voice.move_to(channel)
        else:
            await channel.connect(self_deaf=True)

        await ctx.send(
            f"🔊 **{channel.name}** kanalına geldim."
        )

    except Exception as e:
        await ctx.send(
            f"❌ Ses kanalına giremedim: "
            f"`{type(e).__name__}: {e}`"
        )

# ==========================================
# BOTU BAŞLAT
# ==========================================

bot.run(DISCORD_TOKEN)