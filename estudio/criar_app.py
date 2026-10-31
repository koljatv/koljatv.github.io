#!/usr/bin/env python3
"""Makes 'Estúdio KÖLJA TV.app' (on the Desktop by default): double-click opens the Estúdio in the browser.

  python3 estudio/criar_app.py [destination folder]
"""
import os, plistlib, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import midia  # noqa: E402

DEST = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/Desktop")
APP = os.path.join(DEST, "Estúdio KÖLJA TV.app")
VERSION = open(os.path.join(HERE, "VERSION")).read().strip()

LAUNCHER = """#!/bin/bash
# Estúdio KÖLJA TV: starts the local server (if it isn't running) and opens the page.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
REPO=%s
if [ ! -f "$REPO/estudio/estudio.py" ]; then
  osascript -e 'display alert "Estúdio KÖLJA TV" message "Não achei a pasta do canal em '"$REPO"'. Rode estudio/instalar.command de novo, dentro da pasta do canal."'
  exit 1
fi
PY=$(for p in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do [ -x "$p" ] && echo "$p" && break; done)
mkdir -p "$HOME/Library/Logs"
cd "$REPO" && nohup "$PY" estudio/estudio.py >> "$HOME/Library/Logs/Estudio KOLJA TV.log" 2>&1 &
""" % ("'" + REPO.replace("'", "'\\''") + "'")


def icon(tmp):
    """The KÖLJA TV plate as the app's icon (drawn with PIL; skipped when PIL isn't there)."""
    py = midia.pil_python()
    if not py: return None
    png = os.path.join(tmp, "icon.png")
    code = r'''
import sys
from PIL import Image, ImageDraw, ImageFont
S = 1024
im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
d.rounded_rectangle([60, 60, S - 60, S - 60], radius=200, fill=(18, 14, 10, 255))
d.rounded_rectangle([60, 60, S - 60, S - 60], radius=200, outline=(255, 176, 0, 255), width=24)
f = ImageFont.truetype("/System/Library/Fonts/Supplemental/Futura.ttc", 250, index=2)
d.text((S / 2, 400), "KÖLJA", font=f, fill=(246, 236, 214, 255), anchor="mm")
d.rounded_rectangle([S / 2 - 190, 560, S / 2 + 190, 820], radius=50, fill=(255, 176, 0, 255))
d.text((S / 2, 694), "TV", font=ImageFont.truetype("/System/Library/Fonts/Supplemental/Futura.ttc", 200, index=2), fill=(20, 16, 10, 255), anchor="mm")
im.save(sys.argv[1])
'''
    if subprocess.run([py, "-c", code, png], capture_output=True).returncode: return None
    iset = os.path.join(tmp, "icon.iconset")
    os.makedirs(iset)
    for s in (16, 32, 128, 256, 512):
        for k in (1, 2):
            subprocess.run(["sips", "-z", str(s * k), str(s * k), png, "--out", os.path.join(iset, "icon_%dx%d%s.png" % (s, s, "@2x" if k == 2 else ""))], capture_output=True)
    icns = os.path.join(tmp, "icon.icns")
    return icns if subprocess.run(["iconutil", "-c", "icns", iset, "-o", icns], capture_output=True).returncode == 0 else None


def main():
    if os.path.exists(APP): shutil.rmtree(APP)
    os.makedirs(os.path.join(APP, "Contents", "MacOS"))
    os.makedirs(os.path.join(APP, "Contents", "Resources"))
    exe = os.path.join(APP, "Contents", "MacOS", "estudio")
    with open(exe, "w") as f: f.write(LAUNCHER)
    os.chmod(exe, 0o755)
    info = {"CFBundleName": "Estúdio KÖLJA TV", "CFBundleDisplayName": "Estúdio KÖLJA TV", "CFBundleIdentifier": "tv.kolja.estudio",
            "CFBundleExecutable": "estudio", "CFBundlePackageType": "APPL", "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION, "LSMinimumSystemVersion": "11.0", "NSHighResolutionCapable": True}
    with tempfile.TemporaryDirectory() as tmp:
        ic = icon(tmp)
        if ic:
            shutil.copy(ic, os.path.join(APP, "Contents", "Resources", "icon.icns"))
            info["CFBundleIconFile"] = "icon"
    with open(os.path.join(APP, "Contents", "Info.plist"), "wb") as f: plistlib.dump(info, f)
    subprocess.run(["touch", APP])
    print(APP)


if __name__ == "__main__":
    main()
