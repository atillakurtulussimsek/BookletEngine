#!/usr/bin/env bash
# ============================================================
#  Booklet Engine — Tek tıkla çalıştırma scripti
# ============================================================

# Scriptin bulunduğu dizine geç (her yerden çalışabilsin)
cd "$(dirname "$0")" || exit 1

echo "========================================"
echo "  Booklet Engine v1.0.0"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

# Sanal ortam kontrolü ve aktivasyonu
if [ -d ".venv" ]; then
    echo "Sanal ortam aktif ediliyor..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "Sanal ortam aktif ediliyor..."
    source venv/bin/activate
else
    echo "[UYARI] Sanal ortam bulunamadı, sistem Python'u kullanılıyor."
    echo "        Sanal ortam oluşturmak için: python3 -m venv .venv"
    echo ""
fi

# Python kontrolü
if command -v python3 &>/dev/null; then
    PY=python3
elif command -v python &>/dev/null; then
    PY=python
else
    echo "[HATA] Python bulunamadı! Lütfen Python 3.10+ kurun."
    read -rp "Çıkmak için Enter'a basın..."
    exit 1
fi

echo "Python: $($PY --version)"
echo ""

# Çalıştır
$PY -m src.cli run --config config.json
EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ İşlem başarıyla tamamlandı."
elif [ $EXIT_CODE -eq 2 ]; then
    echo "⚠ İşlem tamamlandı fakat bazı hatalar oluştu. Loglara bakın."
else
    echo "✗ İşlem başarısız oldu (çıkış kodu: $EXIT_CODE)."
fi

echo ""
read -rp "Çıkmak için Enter'a basın..."
