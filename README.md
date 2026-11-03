# DosyaBul 1.10.1 — Windows için Rofi tarzı arama

Ekranın ortasında küçük bir panel olarak açılan; uygulama, komut, dosya, pencere ve web araması yapan yerel Windows başlatıcısı.

## Kullanım

1. `dist\DosyaBul\DosyaBul.exe` dosyasını aç.
2. Daha sonra paneli açmak veya gizlemek için varsayılan **Alt + F2** tuşlarına bas.
3. Uygulama, dosya ya da klasör adını yaz; `Enter` veya çift tık ile aç.
4. `Esc` paneli gizler. Uygulama arka planda hazır kalır.

Panel başlık çubuğu ve görev çubuğu düğmesi olmadan etkin monitörün ortasında açılır. Referans Rofi görünümündeki gibi mor ince çerçeve, koyu gövde, üstte vurgu rengiyle kaplanmış tek arama alanı, küçük ikonlar ve seçili satır için koyu yüzey vurgusu kullanır. Yazı tipi **Cascadia Code**'dur. Alt durum/sonuç alanı ve yükleme çubuğu yoktur.

## Kip sistemi

Rofi'nin "modi" yapısına benzer bir kip sistemi vardır. Kipi **Tab** veya **Ctrl+Tab** ile değiştir; sağ üstteki etiket aktif kipi gösterir.

| Kip | İşlev |
| --- | --- |
| Tümü | Uygulama, dosya, komut, web ve pencereleri birlikte arar; boşken son kullanılanları gösterir |
| Uygulamalar | **Ana sayfa**: başlat menüsü/UWP uygulamaları; boşken son kullanılanlar. `/komut` yazılırsa komut da çalışır |
| Dosyalar | Yalnızca indekslenmiş dosya ve klasörler |
| Komutlar | `/komut` yazarak terminale gönder |
| Web | Doğrudan web araması veya adres açma |
| Pencereler | Açık pencereleri arar ve öne getirir |

## Sistem tepsisi

Uygulama açılışta sistem tepsisine bir ikon ekler:

- **Sol tık**: paneli göster / gizle.
- **Sağ tık**: Göster/Gizle, Ayarlar, Yenile ve Çıkış içeren menü.
- Pencereyi kapat (X) → varsayılan olarak **tepsiye küçülür**. Tamamen kapatmak için tepsi menüsünden **Çıkış** veya `Ctrl+Q` kullan.
- Ayarlardan "Kapatınca sistem tepsisine küçült" kapatılırsa X tuşu uygulamayı kapatır.

## Görünüm ve renk

- **Tema**: KooL Mocha, Nord, Gruvbox, Tokyo Night, Solarized.
- **Vurgu rengi**: Arama kutusunu, panel çerçevesini ve seçimi boyar. Hazır renk düğmeleri (Mavi, Mor, Yeşil, Turkuaz, Kırmızı, Turuncu, Sarı, Pembe) veya serbest `#RRGGBB` kodu. "Tema rengi" düğmesi temanın rengine döner.
- Panel genişliği, görünür satır sayısı, yazı boyutu, satır yüksekliği ve saydamlık ayarlanabilir.

Sonuçlarda uygulamalar Windows'tan çıkarılan **gerçek logolarıyla** gösterilir; Başlat menüsü kısayollarındaki sol alt köşe "kısayol oku" yerleşimi çizilmez. Logo bulunamazsa genel uygulama ikonuna düşülür.

## Uygulamalar ve terminal komutları

- `terminal` yazıldığında WezTerm ilk sırada; ardından Windows Terminal, PowerShell ve Komut İstemi gösterilir.
- Başlat menüsü kısayolları, klasik masaüstü uygulamaları ve `Get-StartApps` ile bulunan Windows uygulamaları aranır. Aynı ada sahip kayıtlı bir uygulama varsa yerleşik tanım yerine o kullanılır.
- Başına `/` koyulan ifade terminal komutudur. Örneğin `/oc` sonucu seçilip `Enter` basıldığında **WezTerm** açılır ve `oc` komutu PowerShell profiliyle çalıştırılır.
- `/git status`, `/python --version` gibi komutlar da aynı şekilde çalışır. `Uygulamalar` kipinde de `/` ile başlayan ifade komut olarak işlenir; yani dosya indeksine dokunmadan hızlıca komut çalıştırabilirsin.
- Panel boş sorguyla açıldığında DosyaBul'dan **en son açılan 5 uygulama ve komut** "Son kullanılanlar" olarak listelenir; `Enter` ile doğrudan yeniden açılabilir. Bu liste `%LOCALAPPDATA%\DosyaBul\history.json` dosyasında saklanır.

Komut, kullanıcı tarafından açıkça yazıldığı biçimde WezTerm içindeki PowerShell'e gönderilir. Güvenmediğin komutları çalıştırma. Ayarlardan WezTerm, Windows Terminal veya doğrudan PowerShell seçilebilir; komutların çalışma klasörü de değiştirilebilir.

WezTerm seçiliyken konsol sarmalayıcı `wezterm.exe` kullanılmaz; doğrudan `wezterm-gui.exe start --cwd ...` çağrılır. Böylece arkada ikinci PowerShell/Windows Terminal penceresi görünmez.

## Web araması ve site açma

- `!youtube` → varsayılan tarayıcıda “youtube” araması yapar.
- `!komik kedi videoları` → ifadenin tamamını web'de arar.
- `!youtube.com` → `https://youtube.com` adresini doğrudan açar.
- `!github.com/JaKooLit` → ilgili sayfayı doğrudan açar.
- `!https://example.com/path` → açık HTTP(S) adresini olduğu gibi açar.

Doğrudan açma yalnızca geçerli HTTP(S) adresleri ve alan adları içindir; `javascript:` gibi şemalar çalıştırılmaz ve normal arama metni kabul edilir. Arama motoru ayarlardan Google, DuckDuckGo veya Bing olarak seçilebilir.

## Program kaldırma

- `-r stremio` → kurulu programlar kayıt defterinden aranır; eşleşmeler listelenir.
- Bir sonucu seçip `Enter` → onay sorulduktan sonra programın kaldırma sihirbazı açılır.
- Arama program adı ve üretici adı üzerinden yapılır; tam eşleşme en üstte gösterilir.
- Kayıtlar HKLM (64/32 bit) ve HKCU kayıt defteri dallarındaki kaldırma girdilerinden okunur; yamalar ve sistem bileşenleri listelenmez.
- Kaldırıcı, programın kendi sihirbazını (Inno Setup, NSIS, MSI vb.) kendi arayüzüyle açar; onay verilmeden hiçbir şey silinmez.

## Rofi ayarları

**Ctrl + ,** ile ayarlar açılır. Arama alanına `rofi ayar`, `DosyaBul Ayarları` veya `-s` yazmak da aynı pencereyi getirir.

Değiştirilebilen seçenekler:

- Tuş birleşimine doğrudan basılarak kaydedilen tamamen özel genel kısayol,
- aynı anda görünen sonuç sayısı: 5, 7, 10 veya 12,
- panel genişliği: 320–800 piksel,
- panel konumu: üst/orta/alt × sol/orta/sağ,
- panelin açılacağı ekran: fare imleci, ana ekran veya etkin pencere,
- panel saydamlığı,
- web arama motoru,
- `/komut` için terminal uygulaması: WezTerm, Windows Terminal veya PowerShell,
- uygulama araması ve dosya araması,
- dışarı tıklayınca gizleme,
- açılışta dosya indeksini yenileme,
- Windows ile birlikte başlatma,
- Windows başlangıcında paneli gösterme veya yalnızca arka planda başlatma,
- `/komut` için terminal çalışma klasörü.

Kısayol alanına tıklayıp istediğin birleşime basman yeterlidir; örneğin `Ctrl+Space`, `Win+/` veya `Ctrl+Alt+K`. Bir genel kısayolda Win, Ctrl, Alt veya Shift değiştiricilerinden en az biri bulunmalıdır. Değişiklik kaydedildiği anda uygulanır. Birleşim Windows ya da başka bir uygulama tarafından kullanılıyorsa eski çalışan kısayol korunur.

Çoklu monitörde panel varsayılan olarak **fare imlecinin bulunduğu ekranda** açılır. Sabit davranış istersen “Ana ekran”; son kullanılan uygulamayı takip etmesini istersen “Etkin pencerenin ekranı” seçilebilir. Panel konumu, seçilen ekranın çalışma alanına göre hesaplanır.

## Neden varsayılan Alt + F2? Win + Space neden kullanılamıyor?

- `Win + Space`, Windows'un dil/klavye değiştiricisidir. Windows `RegisterHotKey` API'si bu birleşimi **1409 — zaten kayıtlı** hatasıyla reddeder.
- Bu birleşimi zorla ele geçirmek düşük seviyeli klavye kancası gerektirir ve Windows'un dil değiştirme işlevini bozar; uygulama bunu yapmaz.
- `Alt + F2`, Linux masaüstlerinde çalıştırıcı açmak için alışıldık, kısa ve iki tuşlu bir birleşimdir.
- İstersen ayarlardan Windows'un kabul ettiği başka herhangi bir birleşimi kaydedebilirsin.

Başka bir uygulama birleşimi kullanıyorsa ayarlar penceresi kısayolun kaydedilemediğini bildirir. Uygulama içinde `Ctrl+Q` işlemi tamamen sonlandırır.

## Windows ile birlikte başlatma

`KisayoluEtkinlestir.cmd` dosyasına çift tıkla. Çağırdığı PowerShell betiği:

- EXE'yi `%LOCALAPPDATA%\Programs\DosyaBul` altına kopyalar,
- Başlat menüsü kısayolu oluşturur,
- Windows oturumu açıldığında `--background` ile sessizce başlatır; panel ekrana gelmez, kısayolla açılır,
- hemen ardından ayarlanan kısayolu etkinleştirir; ilk kurulum varsayılanı **Alt + F2**'dir.

Geri almak için `KisayoluKaldir.cmd` dosyasına çift tıkla. Bu işlem arama indeksini silmez. Hiçbir betik yönetici yetkisi gerektirmez.

Komut satırından görünmeden başlatmak da mümkündür:

```powershell
DosyaBul.exe --background
```

Uygulama zaten açıksa EXE'yi tekrar çalıştırmak ikinci bir pencere oluşturmaz; mevcut paneli gösterir. `--background` ile yapılan tekrar çalıştırmalar paneli açmaz, bu yüzden otomatik başlangıç ikinci kez tetiklense bile ekrana bir şey gelmez.

## Görünüm

Görsel yaklaşım, JaKooLit'in güncel Hyprland-Dots projesindeki varsayılan **KooL Style 4** ve LonerOrZ tarzından Windows'a uyarlanmıştır:

- ortalanmış, dar ve dikey panel,
- mor ince dış çerçeve ve koyu yarı saydam yüzey,
- vurgu rengiyle kaplanmış üst arama alanı ve koyu seçili satır,
- Cascadia Code yazı tipi,
- küçük sol ikonlar ve yalnızca sonuç adı,
- köşeli Rofi görünümü,
- tek sütunda ayarlanabilir 5, 7, 10 veya 12 görünür sonuç.

Kaynak tema: <https://github.com/JaKooLit/Hyprland-Dots/tree/main/config/rofi/themes>

Bu uygulama Rofi kodunu içermez; Tkinter ve Windows API ile aynı etkileşim yaklaşımını uygular. Duvar kâğıdından otomatik renk üretmek yerine okunabilir sabit bir koyu palet kullanır.

## Arama ve indeks davranışı

- Klasör seçmek gerekmez. C:, D:, USB ve eşlenmiş Windows sürücüleri otomatik algılanır.
- Panel **Uygulamalar** kipinde açılır: ana sayfada dosya indeksine hiç dokunulmaz, bu yüzden uygulama araması anında yanıt verir. Dosya araması için `Ctrl+Tab` ile **Dosyalar** veya **Tümü** kipine geç.
- Uygulamalar, dosyalar ve klasörler aynı listede aranır; uygulamalar önce gösterilir (Tümü kipinde).
- Dosya indeksi yoksa ilk açılışta yalnızca bir kez arka planda hazırlanır.
- Sonraki açılışlarda kayıtlı indeks anında kullanılır; disk sürekli veya periyodik olarak yeniden taranmaz.
- Yeni, silinen veya taşınan dosyalar için `F5` kullanılır. İstenirse ayarlardan “Açılışta dosya indeksini yenile” etkinleştirilebilir.
- Uygulama listesi program açılırken ve panel öne geldiğinde (en fazla 15 saniyede bir) yenilenir; yeni kurulan bir program için `F5` beklemene gerek kalmaz. `F5` hem uygulamaları hem dosya indeksini hemen yeniler.
- Türkçe karakter ve büyük/küçük harf farkları önemsenmez: `is plani`, `İş Planı` sonucunu bulur.
- Boş sorguda tüm diski listelemek yerine küçük panel halinde bekler; daha önce açılmış uygulama ve komutlar varsa son 5 tanesi listelenir.
- En fazla 500 sonuç tutulur; panelde aynı anda ayarlanan sayıda satır görünür ve liste kaydırılabilir.

Kısayollar:

| Kısayol | İşlev |
| --- | --- |
| `Alt + F2` | Varsayılan olarak paneli aç / gizle; ayarlardan değiştirilebilir |
| `Ctrl + ,` | Rofi ayarlarını aç |
| `Tab` / `Ctrl + Tab` | Kipi ileri al (Tümü, Uygulamalar, Dosyalar, Komutlar, Web, Pencereler) |
| `Shift + Tab` / `Ctrl + Shift + Tab` | Kipi geri al |
| `Esc` | Paneli gizle ve sorguyu temizle |
| `Enter` | Seçili öğeyi aç |
| `Shift + Enter` | Öğeyi Dosya Gezgini'nde göster |
| `Ctrl + C` | Seçili öğenin yolunu kopyala |
| `Ctrl + F`, `Ctrl + K`, `F3` | Arama alanına odaklan |
| `F5` | Uygulama listesini ve dosya indeksini yenile |
| `Ctrl + Q` | Arka plan uygulamasını tamamen kapat |

Sağ tık menüsünde açma, klasörde gösterme, yol kopyalama ve ayarlar bulunur.

## Gizlilik ve sınırlar

- Dosya içerikleri okunmaz; yalnızca ad, yol, tür, boyut ve tarih üst verileri indekslenir.
- İndeks `%LOCALAPPDATA%\DosyaBul\index.sqlite3` dosyasındadır.
- Ayarlar `%LOCALAPPDATA%\DosyaBul\settings.json` dosyasındadır.
- Son kullanılan uygulama ve komutlar `%LOCALAPPDATA%\DosyaBul\history.json` dosyasında, yalnızca yerelde tutulur.
- Telemetri, hesap veya internet servisi yoktur. Eşlenmiş ağ ve bulut sürücülerinin kendi bağlantıları ayrı konudur.
- `!` web kipi yalnızca seçilen arama motorunu veya yazdığın HTTP(S) adresini varsayılan tarayıcıya gönderir.
- Korumalı alanlar, Geri Dönüşüm Kutusu ve `System Volume Information` atlanır.
- Sembolik bağlantılar izlenmez; junction klasörleri listelenir ama içine girilmez.
- Uygulama gerçek dosyaları silmez.
- Çalıştırılabilir dosya ve betikler açılmadan önce onay istenir.
- EXE yerel olarak oluşturulur ve dijital imzalı değildir; Windows güvenlik uyarısı gösterebilir.

## Geliştirme ve test

Çalışma bağımlılığı yoktur; standart Windows Python 3.10+ içindeki Tkinter ve SQLite yeterlidir.

```powershell
python run.py
python run.py --background
python -m unittest discover -s tests -t . -v

# EXE üretimi için:
python -m pip install "pyinstaller>=6,<7"
.\ExeOlustur.ps1

# Paketlenmiş EXE ve kısayol davranışı:
$env:PYTHONPATH = (Get-Location)
python tools\smoke_windows.py dist\DosyaBul\DosyaBul.exe
```

`dosyabul\hotkey.py`, serbestçe kaydedilebilen Windows `RegisterHotKey` birleşimini; `applications.py`, Başlat menüsü/UWP uygulamalarını ve `/komut` kipini; `websearch.py`, `!` web kipini; `settings.py`, kalıcı ayarları yönetir. `windowing.py`, seçilen monitör konumunu ve panel boyutunu uygular. Grafik oturumu olmayan ortamlarda arayüz testleri atlanır.
