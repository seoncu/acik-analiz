#!/bin/bash
# ============================================
# Açık Analiz — macOS Başlatıcı
# Çift tıklayarak çalıştırın
# ============================================

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║  📊 Açık Analiz — Başlatılıyor...              ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""

# Python 3 kontrolü
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo "❌ Python bulunamadı!"
    echo ""
    echo "Python 3 yüklemeniz gerekiyor:"
    echo "  brew install python3"
    echo "  veya: https://www.python.org/downloads/"
    echo ""
    read -p "Devam etmek için Enter'a basın..."
    exit 1
fi

echo "🐍 Python: $($PYTHON --version)"

# Bağımlılıkları kontrol et ve gerekirse kur
echo "📦 Bağımlılıklar kontrol ediliyor..."
$PYTHON -c "import polars, fastapi, uvicorn, scipy, numpy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📥 İlk kullanım: Bağımlılıklar yükleniyor (bir kez)..."
    echo ""
    $PYTHON -m pip install --break-system-packages -q -r "$DIR/server/requirements.txt" 2>/dev/null || \
    $PYTHON -m pip install -q -r "$DIR/server/requirements.txt"

    if [ $? -ne 0 ]; then
        echo "❌ Bağımlılıklar yüklenemedi."
        echo "Manuel yükleme: pip3 install polars numpy scipy fastapi uvicorn python-multipart"
        read -p "Devam etmek için Enter'a basın..."
        exit 1
    fi
    echo "✅ Bağımlılıklar yüklendi!"
fi

echo ""
echo "🚀 Python Motor başlatılıyor (port 8765)..."
echo "   Motor durdurmak için: Ctrl+C"
echo ""
$PYTHON "$DIR/server/engine.py"
