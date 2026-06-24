#!/bin/bash
# ============================================================
# Açık Analiz — macOS Başlatıcı (ince + otomatik güncelleme)
# Çift tıklayın. İlk seferde sağ tık → Aç (Gatekeeper) gerekebilir.
# Her açılışta en güncel sürümü GitHub'dan çeker.
# ============================================================
chmod +x "$0" 2>/dev/null
xattr -d com.apple.quarantine "$0" 2>/dev/null

DIR="$HOME/.acikanaliz"
mkdir -p "$DIR"
BASE="https://raw.githubusercontent.com/seoncu/acik-analiz/main"

_notify(){ osascript -e "display notification \"$1\" with title \"Açık Analiz\"" 2>/dev/null; }
_alert(){ osascript -e "display dialog \"$1\" with title \"Açık Analiz\" buttons {\"Tamam\"} default button 1 with icon caution" 2>/dev/null; }

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
_notify "Hazırlanıyor... İlk açılış birkaç dakika sürebilir."

# 1) uv (yoksa kur — yalnızca ilk kullanımda internet)
if ! command -v uv &>/dev/null; then
  if ! curl -sf --max-time 8 https://astral.sh >/dev/null 2>&1; then
    _alert "İnternet bağlantısı gerekiyor (ilk kurulum için)."; exit 1
  fi
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
if ! command -v uv &>/dev/null; then _alert "Kurulum aracı (uv) yüklenemedi."; exit 1; fi

# 2) En güncel dosyaları çek (engine + köprü + arayüz + bağımlılıklar)
_notify "Güncel sürüm indiriliyor..."
for f in server/engine.py server/api-bridge.js server/requirements.txt index.html; do
  curl -fsSL "$BASE/$f" -o "$DIR/$(basename "$f")" 2>/dev/null
done
# Arayüzün beklediği yol: /server/api-bridge.js → motor bunu kendi sunar (kopya da bırak)
mkdir -p "$DIR/server"; cp "$DIR/api-bridge.js" "$DIR/server/api-bridge.js" 2>/dev/null
if [ ! -f "$DIR/engine.py" ]; then _alert "Motor dosyası indirilemedi. İnternet bağlantınızı kontrol edin."; exit 1; fi

# 3) Motoru başlat (sabit Python 3.12 + izole ortam) ve tarayıcıyı aç
cd "$DIR"
( sleep 9; open "http://127.0.0.1:8765" 2>/dev/null ) &
_notify "Motor başlatılıyor (port 8765)..."
uv run --python 3.12 --with-requirements "$DIR/requirements.txt" "$DIR/engine.py"
echo "Motor durdu. Bu pencereyi kapatabilirsiniz."
read -p "Çıkmak için Enter..."
