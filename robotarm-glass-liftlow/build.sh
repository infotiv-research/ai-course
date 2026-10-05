#!/usr/bin/env bash
# Build robotarm_glass_liftlow_audio.mp4 from scratch. Everything runs in Docker; nothing is installed on the host.
#   ./build.sh                 full render -> out/robotarm_glass_liftlow_audio.mp4
#   GPU=1 ./build.sh           render on another GPU (default 0)
#   ./build.sh --audio-only    re-make the sound track and re-mux, no re-render
set -euo pipefail
cd "$(dirname "$0")"
IMAGE=robotarm-glass-blender:5.2.2
NAME=robotarm_glass_liftlow
RUN=(docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD":/work -w /work)

docker image inspect "$IMAGE" >/dev/null 2>&1 || docker build -t "$IMAGE" .
mkdir -p out

if [ "${1:-}" != "--audio-only" ]; then
    rm -rf out/frames
    # 1. frames (Cycles, OptiX), 240 PNGs = 8 s at 30 fps
    "${RUN[@]}" --gpus "device=${GPU:-0}" "$IMAGE" -b -P scene.py
    # 2. silent video
    "${RUN[@]}" --entrypoint ffmpeg "$IMAGE" -y -loglevel error -framerate 30 -i out/frames/f_%04d.png \
        -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -movflags +faststart "out/$NAME.mp4"
    rm -rf out/frames
fi
# 3. sound track (numpy synth in Blender's bundled Python)
"${RUN[@]}" "$IMAGE" -b --factory-startup -P audio.py -- "out/$NAME.wav"
# 4. mux
"${RUN[@]}" --entrypoint ffmpeg "$IMAGE" -y -loglevel error -i "out/$NAME.mp4" -i "out/$NAME.wav" \
    -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart "out/${NAME}_audio.mp4"
echo "wrote out/${NAME}_audio.mp4"
