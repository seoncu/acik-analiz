# Tek dosya masaüstü uygulaması (.app / .exe)

Bu klasör, Python motorunu **çift-tıkla çalışan tek bir dosya** olarak paketlemek
içindir. Son kullanıcıda **Python, pip veya terminal GEREKMEZ** — indir, aç, kullan.

## Nasıl çalışır?

- `launcher.py` — PyInstaller giriş noktası. Gömülü `server/engine.py`'yi başlatır,
  motor hazır olunca tarayıcıyı otomatik açar (127.0.0.1:8765).
- `.github/workflows/build-desktop.yml` — GitHub Actions ile **macOS ve Windows**
  ikililerini otomatik derler.

## Çalıştırmak için (TEK SEFERLİK kurulum)

1. **`server/` klasörünü depoya ekleyin** (kök dizine): `server/engine.py` ve
   `server/requirements.txt`. (Workflow bunlar olmadan hata verip durur.)
   - Tekrarlanabilirlik için `requirements.txt`'te sürümleri sabitlemeniz önerilir
     (örn. `polars==1.12.0`).
2. GitHub'da depo sayfası → **Actions** sekmesi → **"Masaüstü uygulama derle"** →
   **Run workflow**. (Veya `git tag v1.0 && git push --tags` ile otomatik tetiklenir
   ve bir **Release** oluşturup dosyaları oraya ekler.)
3. Derleme bitince **Artifacts**'tan indirin:
   - `AcikAnaliz-macOS.zip` → içinden `AcikAnaliz.app`
   - `AcikAnaliz-Windows` → `AcikAnaliz.exe`

## Son kullanıcıya dağıtım

İkili dosyayı (veya Release linkini) paylaşın. Kullanıcı:

- **macOS:** `AcikAnaliz.app` → çift tıkla. İlk seferde "tanımlanamayan geliştirici"
  uyarısı gelirse **sağ tık → Aç → Aç** (yalnızca bir kez).
- **Windows:** `AcikAnaliz.exe` → çift tıkla. SmartScreen uyarısı gelirse
  **"Daha fazla bilgi" → "Yine de çalıştır"** (yalnızca bir kez).

> Bu uyarılar, uygulama **kod imzalama sertifikası ile imzalanmadığı** için çıkar
> (imzalama: Apple Developer hesabı ~99$/yıl, Windows için ayrı sertifika).
> İmzasız da güvenle çalışır; uyarı yalnızca ilk açılışta bir kez görünür.

## Notlar / ince ayar

- `launcher.py` şunu varsayar: `server/engine.py` doğrudan çalıştırıldığında
  sunucuyu **127.0.0.1:8765** üzerinde başlatır (mevcut başlatıcılarla aynı model).
  Port/giriş noktası farklıysa `launcher.py` içindeki `PORT`/`ENGINE`'i düzenleyin.
- Polars eski işlemcide (AVX olmadan) çökerse, `requirements.txt`'te `polars` yerine
  `polars-lts-cpu` kullanın (veya CI'da ek bir "lts" varyantı derleyin).
- Bu iskelet `server/` eklendiğinde çalışır; gerçek `engine.py`'nizle bir derleme
  alıp doğrulamanız (ve gerekirse hidden-import eklemeniz) önerilir.
