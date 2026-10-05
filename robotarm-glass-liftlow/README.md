# INFOTIV robot arm, glass letters: AI course loop

A standalone build of `robotarm_glass_liftlow_audio.mp4`, an 8 s seamless loop at 1920x1080 and 30 fps, with sound.

A white cobot lifts the glass "O" out of INFOTIV, spins it, and sets it back. The glass letters have glowing orange cores, as in `glass.mp4`. A frosted-glass sign reading "AI COURSE / Hamid Ebadi" drops in on two strings, dangles until it settles, and is hoisted out at the end of the loop.

## Build
Requirements: Docker plus the NVIDIA Container Toolkit, and an NVIDIA GPU (OptiX).

```bash
./build.sh                 # -> out/robotarm_glass_liftlow_audio.mp4   (~6 min on an RTX 5070 Ti)
GPU=1 ./build.sh           # use another GPU
./build.sh --audio-only    # change audio.py, re-make the sound and re-mux without re-rendering
```
The first run builds the Docker image: Ubuntu 24.04, Blender 5.2.2 and ffmpeg.

## Files
- `scene.py`: builds the whole scene procedurally and renders the frames to `out/frames/`.
- `audio.py`: synthesises the sound track, timed to the animation, and loops seamlessly.
- `build.sh`: frames, then the H.264 video, then the audio, then the muxed MP4.
- `Dockerfile`: the render image.
- `assets/`: Montserrat fonts (SIL OFL, see `assets/OFL.txt`).

## Tweaks
- Quick stills at half resolution: `docker run --rm --gpus device=0 -v "$PWD":/work -w /work robotarm-glass-blender:5.2.2 -b -P scene.py -- --preview --frames 1,135`
- `--samples N` raises Cycles quality (default 16, denoised).
- Sign text and size are in the `# ---- course placard` block of `scene.py`.
- Drop and dangle motion: `sign_pose()`. Robot path: `PATH` and `LIFT`.

Everything is a function of the loop phase, so frame 241 equals frame 1, and the audio wraps around the same 8 s.
