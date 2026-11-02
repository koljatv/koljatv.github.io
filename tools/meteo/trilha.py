#!/usr/bin/env python3
"""Render the 72-second forecast score and install its music bed.
Prepare the acoustic instruments first with tools/music/approved-v1/prepare_assets.py.
The previous composition remains available in git history.
"""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
if __name__ == '__main__':
    subprocess.run([sys.executable, str(ROOT / 'tools/music/approved-v1/render.py'), '--only', 'previsao'], check=True)
    source = ROOT / 'media/trilhas-review/approved-v1/previsao.m4a'
    shutil.copyfile(source, Path(__file__).with_name('trilha.m4a'))
    print('Installed the complete 72-second forecast score.')
