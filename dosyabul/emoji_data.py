"""Emoji ve sembol kipi için küçük, yerleşik liste (Türkçe + İngilizce anahtar sözcükler)."""

from .query import fold_text

# karakter | anahtar sözcükler
_RAW = """
😀|gülümseme yüz mutlu smile grin happy
😂|gülmekten ağlamak komik laugh joy lol
🤣|yerlerde gülmek rofl
😊|tatlı gülümseme blush
😉|göz kırpma wink
😍|aşık kalpli gözler love heart eyes
😘|öpücük kiss
😎|havalı güneş gözlüğü cool sunglasses
🤔|düşünmek think hmm
😐|nötr neutral
😢|üzgün ağlamak sad cry
😭|hüngür ağlamak sob
😡|kızgın angry
🤯|şaşkın patlayan kafa mind blown
😴|uyku sleep
🥳|parti kutlama party
🙃|ters yüz gülümseme upside down
😅|terli gülümseme sweat smile
🥲|duygulu gülümseme
😇|melek angel
🤗|sarılma hug
🙄|göz devirme eye roll
😬|dişler grimace
😱|korku scream fear
🤮|kusmak sick vomit
🤒|hasta sick
🥰|sevgi love
👍|beğen onay tamam thumbs up like ok
👎|beğenme thumbs down dislike
👏|alkış clap
🙏|dua teşekkür lütfen pray thanks please
👋|el sallamak merhaba wave hello
🤝|el sıkışma anlaşma handshake deal
💪|kas güç muscle strong
✌️|zafer barış victory peace
🤞|parmak çaprazlama şans fingers crossed
👌|tamam ok
👀|gözler bakmak eyes look
🧠|beyin brain
❤️|kalp aşk heart love red
💔|kırık kalp broken heart
💙|mavi kalp blue heart
💚|yeşil kalp green heart
💜|mor kalp purple heart
🔥|ateş yangın fire hot
✨|parıltı yıldız sparkles
⭐|yıldız star
🌟|parlak yıldız glowing star
💯|yüz puan hundred
🎉|kutlama konfeti tada party
🎂|doğum günü pasta birthday cake
🎁|hediye gift
🏆|kupa ödül trophy
🚀|roket rocket launch
💡|ampul fikir idea bulb
⚡|şimşek yıldırım elektrik lightning
☀️|güneş sun
🌙|ay moon
☁️|bulut cloud
🌧️|yağmur rain
❄️|kar kış snow winter
🌈|gökkuşağı rainbow
🌍|dünya world earth
🌹|gül rose
🌸|çiçek kiraz flower blossom
🌲|ağaç çam tree
🍎|elma apple
🍕|pizza
🍔|hamburger burger
🍟|patates kızartması fries
🍫|çikolata chocolate
☕|kahve çay coffee tea
🍺|bira beer
🍷|şarap wine
🐶|köpek dog
🐱|kedi cat
🐻|ayı bear
🦊|tilki fox
🐧|penguen penguin
🐍|yılan python snake
🦄|tek boynuzlu at unicorn
🐛|böcek hata bug
✅|onay tik check done
❌|çarpı hata yanlış cross wrong
⚠️|uyarı dikkat warning
❓|soru question
❗|ünlem exclamation
🔒|kilit lock
🔓|kilit açık unlock
🔑|anahtar key
🔔|zil bildirim bell notification
🔍|ara büyüteç search magnifier
📌|raptiye pin
📎|ataç clip paperclip
📁|klasör folder
📄|belge dosya document file
📝|not yazı memo note
📅|takvim calendar
📧|e-posta mail email
📱|telefon phone mobile
💻|bilgisayar laptop computer
🖥️|masaüstü monitor desktop
⌨️|klavye keyboard
🖱️|fare mouse
🔋|pil battery
🔧|anahtar tamir wrench tool
⚙️|dişli ayar gear settings
🛠️|araçlar tools
🧪|deney test tube
📊|grafik chart
📈|artış yükseliş chart up increase
📉|düşüş chart down decrease
💰|para money
💳|kredi kartı card
🕐|saat clock time
⏰|alarm saat alarm
⌛|kum saati hourglass
🏠|ev home house
🚗|araba car
✈️|uçak airplane plane
🚲|bisiklet bike
⚽|futbol football soccer
🎮|oyun game
🎵|müzik music
🎬|film clip movie
📷|kamera fotoğraf camera photo
→|ok sağ arrow right
←|ok sol arrow left
↑|ok yukarı arrow up
↓|ok aşağı arrow down
⇒|çift ok sağ implies
✓|tik onay check
✗|çarpı cross
•|nokta madde bullet
…|üç nokta ellipsis
©|telif copyright
®|tescil registered
™|marka trademark
°|derece degree
±|artı eksi plus minus
×|çarpı çarpma multiply times
÷|bölme divide
≈|yaklaşık approximately
≠|eşit değil not equal
≤|küçük eşit less equal
≥|büyük eşit greater equal
∞|sonsuz infinity
π|pi
√|karekök sqrt root
€|euro
₺|lira tl turkish lira
$|dolar dollar
£|sterlin pound
¥|yen
½|yarım half
¼|çeyrek quarter
₿|bitcoin
"""


def _load() -> tuple[tuple[str, str, str], ...]:
    rows = []
    for line in _RAW.strip().splitlines():
        character, _, words = line.partition("|")
        if character and words:
            rows.append((character, words, fold_text(words)))
    return tuple(rows)


EMOJIS = _load()


def search_emoji(text: str, limit: int = 60) -> tuple[tuple[str, str], ...]:
    """(karakter, ad) çiftleri; boş sorguda ilk liste döner."""
    terms = tuple(part for part in fold_text(text).split() if part)
    found = []
    for character, words, key in EMOJIS:
        if all(term in key for term in terms):
            found.append((character, words.split()[0]))
            if len(found) >= limit:
                break
    return tuple(found)
