#!/usr/bin/env bash
# Record features.mp4 from the real game: headless Chromium plays each scene in scenes.mjs
# frame by frame, compose.py adds the feature list beside it, ffmpeg encodes it.
# Needs node 22+, chromium, python3 with Pillow, ffmpeg and the DejaVu fonts.
#   ./build.sh            -> ../features.mp4 and ../features-poster.jpg
#   ./build.sh laser      -> record just that scene into out/laser, to check it
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p out
node drive.mjs scenes.mjs out ${1:-}
[ -n "${1:-}" ] && exit 0
python3 compose.py out out/composed
ffmpeg -loglevel error -y -framerate 30 -i out/composed/%05d.png -c:v libx264 -pix_fmt yuv420p \
    -crf 22 -preset slow -tune animation -movflags +faststart -an ../features.mp4
# poster: the banana combo, shown while the video loads
ffmpeg -loglevel error -y -i out/composed/00030.png -q:v 3 ../features-poster.jpg
