#!/bin/bash
# POLIZ Kalkulyatori.app ni yiğadi (faqat macOSda işlaydi).
#
#   ./build_mac.sh
#
# Natija: dist/POLIZ Kalkulyatori.app  va  dist/POLIZ-Kalkulyatori-macOS.zip
# Ilovani Applications papkasiga ötkazing.

set -euo pipefail
cd "$(dirname "$0")"

APP="POLIZ Kalkulyatori"

if [[ "$(uname)" != "Darwin" ]]; then
  echo "Bu skript faqat macOSda işlaydi." >&2
  exit 1
fi

echo "› Virtual muhit va kutubxonalar…"
python3 -m venv .build-venv
source .build-venv/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet pywebview pyinstaller

echo "› Testlar…"
python -m unittest -q

echo "› Ikonka (.icns)…"
rm -rf build/icon.iconset
mkdir -p build/icon.iconset
for size in 16 32 128 256 512; do
  sips -z $size $size assets/icon.png --out "build/icon.iconset/icon_${size}x${size}.png" >/dev/null
  double=$((size * 2))
  sips -z $double $double assets/icon.png --out "build/icon.iconset/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns build/icon.iconset -o build/icon.icns

echo "› Ilova yiğilmoqda…"
pyinstaller --noconfirm --clean --log-level WARN \
  --windowed \
  --name "$APP" \
  --icon build/icon.icns \
  --osx-bundle-identifier uz.poliz.kalkulyator \
  --add-data "ui:ui" \
  poliz_kalkulyator.py

PLIST="dist/$APP.app/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString 2.0" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :LSApplicationCategoryType string public.app-category.education" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :NSRequiresAquaSystemAppearance bool false" "$PLIST" 2>/dev/null || true
codesign --force --deep --sign - "dist/$APP.app"   # ad-hoc imzo (Apple Silicon uçun şart)

echo "› Tekşiriş…"
"dist/$APP.app/Contents/MacOS/$APP" --selftest

ditto -c -k --sequesterRsrc --keepParent "dist/$APP.app" "dist/POLIZ-Kalkulyatori-macOS.zip"

echo
echo "Tayyor: dist/$APP.app"
echo "Örnatiş: open dist   — keyin ilovani Applications papkasiga sudrab taşlang."
