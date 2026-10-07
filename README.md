# PwoxAI - Ucretsiz Windows Discord Botu

Bu sürüm OpenAI API kullanmaz. Sohbet için Google Gemini API'nin ücretsiz katmanındaki modeli kullanır. Google, Gemini API'de ücretsiz giriş/çıkış tokenları olan bir ücretsiz katman sunuyor; limitler modele ve kullanım türüne göre değişebilir.

## Kurulum

1. Bu klasörde `install.bat` dosyasına çift tıkla.
2. `.env.example` dosyasını `.env` olarak kopyala.
3. Google AI Studio'dan bir Gemini API anahtarı oluştur ve `.env` içine `GEMINI_API_KEY=` satırına koy.
4. Discord bot tokenını `DISCORD_TOKEN=` satırına koy.
5. `run.bat` dosyasına çift tıkla.

## Discord komutları

- `/chat mesaj` - PwoxAI ile konuş.
- `/gorsel aciklama` - ücretsiz görsel servisi üzerinden görsel üretmeyi dener.
- `/temizle` - kendi sohbet hafızanı temizler.
- `/yardim` - yardım menüsü.

## Önemli

Gemini'nin ücretsiz API katmanının hız/kullanım limitleri vardır. Görsel komutu ayrı bir ücretsiz görsel servisi kullanır; bu servisin anonim erişimi ve kotaları zamanla değişebilir. Görsel üretimi çalışmazsa bu, Discord botunun çalışmadığı anlamına gelmez.

API anahtarlarını Discord'a veya GitHub'a gönderme.


## `.pwoxai` ile sohbet
Discord Developer Portal > Bot > Privileged Gateway Intents bölümünden **Message Content Intent** seçeneğini aç. Sonra botu yeniden başlat. Discord kanalında `.pwoxai merhaba` yazman yeterli.
