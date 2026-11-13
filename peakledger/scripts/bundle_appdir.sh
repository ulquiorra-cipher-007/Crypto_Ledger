#!/usr/bin/env bash
# ==============================================================================
# PeakLedger AppDir & Single Executable Binary Bundler
# Creates:
#   1. ./PeakLedger & bin/PeakLedger (Universal standalone single executable binary)
#   2. ./PeakLedger-x86_64.AppImage (Standard Linux AppImage)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "========================================================================"
echo "          PEAKLEDGER STANDALONE EXECUTABLE BUNDLER                      "
echo "========================================================================"

# 1. Ensure C++ backend and tests are compiled
echo "[1/6] Compiling PeakLedger C++ backend..."
make -j"$(nproc)"

# 2. Setup AppDir directories
echo "[2/6] Assembling AppDir file structure..."
mkdir -p AppDir/usr/bin AppDir/usr/lib AppDir/ui AppDir/models bin

# Copy C++ backend
cp bin/forensic_backend AppDir/usr/bin/forensic_backend
chmod +x AppDir/usr/bin/forensic_backend

# Copy UI components
cp -r ui/* AppDir/ui/

# Copy models
if [ -d models ] && [ "$(ls -A models 2>/dev/null)" ]; then
    cp -r models/* AppDir/models/ 2>/dev/null || true
fi

# Copy key runtime libraries if available to ensure portability
echo "[3/6] Bundling dynamic dependencies into AppDir/usr/lib..."
LIBS_TO_BUNDLE=(
    /usr/lib/x86_64-linux-gnu/libsqlite3.so*
    /usr/local/cuda/targets/x86_64-linux/lib/libcudart.so*
)

for libpattern in "${LIBS_TO_BUNDLE[@]}"; do
    for libfile in $libpattern; do
        if [ -f "$libfile" ] && [ ! -L "$libfile" ]; then
            cp -u "$libfile" AppDir/usr/lib/ 2>/dev/null || true
        fi
    done
done

# 3. Ensure AppRun, Desktop entry, and Icons are present
echo "[4/6] Verifying AppRun launcher and Desktop integration..."
if [ ! -f AppDir/AppRun ]; then
    cat << 'EOF' > AppDir/AppRun
#!/usr/bin/env bash
set -e
if [ -z "${APPDIR:-}" ]; then
    APPDIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
fi
export APPDIR
export LD_LIBRARY_PATH="${APPDIR}/usr/lib:${APPDIR}/usr/lib/x86_64-linux-gnu:/usr/local/cuda/lib64:/usr/lib/wsl/lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export PATH="${APPDIR}/usr/bin:${PATH}"
export PYTHONPATH="${APPDIR}/ui:${APPDIR}:${PYTHONPATH:-}"

if [ "$#" -eq 0 ]; then
    exec python3 "${APPDIR}/ui/main.py"
fi

case "$1" in
    --ui)
        shift
        exec python3 "${APPDIR}/ui/main.py" "$@"
        ;;
    --cli)
        shift
        exec "${APPDIR}/usr/bin/forensic_backend" "$@"
        ;;
    --ingest|--verify|--info|--list|--clean-frames|-h|--help)
        exec "${APPDIR}/usr/bin/forensic_backend" "$@"
        ;;
    *)
        if [[ "$1" == -* ]]; then
            exec "${APPDIR}/usr/bin/forensic_backend" "$@"
        else
            exec python3 "${APPDIR}/ui/main.py" "$@"
        fi
        ;;
esac
EOF
fi
chmod +x AppDir/AppRun

# Desktop Entry
cat << 'EOF' > AppDir/peakledger.desktop
[Desktop Entry]
Type=Application
Name=PeakLedger
GenericName=Cryptographic Video Forensic Workstation
Comment=High-Performance GPU-Accelerated Cryptographic Video Forensic Engine & Biometric Intelligence Backend
Exec=AppRun %F
Icon=peakledger
Terminal=false
Categories=Utility;Security;AudioVideo;Video;
Keywords=forensics;crypto;video;merkle;tamper;
EOF

# Ensure icons exist
if [ ! -f AppDir/peakledger.png ]; then
    python3 -c "
from PIL import Image, ImageDraw
img = Image.new('RGBA', (256, 256), color=(15, 23, 42, 255))
draw = ImageDraw.Draw(img)
draw.polygon([(128, 20), (220, 50), (220, 160), (128, 236), (36, 160), (36, 50)], fill=(30, 41, 59), outline=(56, 189, 248), width=6)
draw.ellipse((88, 80, 168, 160), outline=(14, 165, 233), width=5)
draw.ellipse((108, 100, 148, 140), fill=(56, 189, 248))
img.save('AppDir/peakledger.png', format='PNG')
img.save('AppDir/.DirIcon', format='PNG')
" 2>/dev/null || true
fi

# 4. Generate the Universal Standalone Single Executable Binary
echo "[5/6] Generating Universal Standalone Single Executable: PeakLedger..."
STAGE_TAR="/tmp/peakledger_payload_$$.tar.gz"
tar -czf "$STAGE_TAR" -C AppDir .

cat << 'EOF' > bin/PeakLedger
#!/usr/bin/env bash
# ==============================================================================
# PeakLedger Universal Single Executable Binary
# Self-contained executable: forensic C++ engine + analyst GUI + ML weights
# Compatible across Linux (Ubuntu, Xubuntu, Debian, Arch, Fedora) and WSL2.
# ==============================================================================
set -e

# Cache directory anchored to user cache with unique binary digest
SELF_HASH="$(head -c 1024 "$0" | md5sum | awk '{print $1}')"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/peakledger/bundle_${SELF_HASH}"

if [ ! -f "${CACHE_DIR}/.installed" ]; then
    mkdir -p "${CACHE_DIR}"
    PAYLOAD_LINE=$(awk '/^__PAYLOAD_START__/ {print NR + 1; exit 0; }' "$0")
    tail -n +"${PAYLOAD_LINE}" "$0" | tar -xz -C "${CACHE_DIR}"
    touch "${CACHE_DIR}/.installed"
fi

export APPDIR="${CACHE_DIR}"
exec "${CACHE_DIR}/AppRun" "$@"
exit 0
__PAYLOAD_START__
EOF

# Append compressed payload
cat "$STAGE_TAR" >> bin/PeakLedger
rm -f "$STAGE_TAR"
chmod +x bin/PeakLedger
cp -f bin/PeakLedger ./PeakLedger

echo "[+] Universal single executable binary successfully built: ./PeakLedger ($(du -h ./PeakLedger | cut -f1))"

# 5. Build Standard AppImage if appimagetool or mksquashfs is available
echo "[6/6] Generating Standard AppImage: PeakLedger-x86_64.AppImage..."
APPIMAGE_BUILT=0

if [ -x /tmp/squashfs-root/AppRun ]; then
    ARCH=x86_64 /tmp/squashfs-root/AppRun AppDir PeakLedger-x86_64.AppImage >/dev/null 2>&1 || true
    if [ -f PeakLedger-x86_64.AppImage ]; then
        chmod +x PeakLedger-x86_64.AppImage
        echo "[+] AppImage successfully created: ./PeakLedger-x86_64.AppImage ($(du -h ./PeakLedger-x86_64.AppImage | cut -f1))"
        APPIMAGE_BUILT=1
    fi
fi

if [ "$APPIMAGE_BUILT" -eq 0 ] && command -v mksquashfs >/dev/null 2>&1; then
    mksquashfs AppDir PeakLedger.squashfs -root-owned -noappend -comp zstd >/dev/null 2>&1 || true
    echo "[+] SquashFS archive created: ./PeakLedger.squashfs"
fi

echo "========================================================================"
echo "[SUCCESS] PeakLedger standalone packaging complete!"
echo "  Executable 1 (Universal Binary): ./PeakLedger"
echo "  Executable 2 (Standard AppDir) : ./AppDir/AppRun"
if [ -f PeakLedger-x86_64.AppImage ]; then
    echo "  Executable 3 (Linux AppImage)  : ./PeakLedger-x86_64.AppImage"
fi
echo "========================================================================"
