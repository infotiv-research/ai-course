# Headless Blender with NVIDIA GPU rendering (CUDA/OptiX via nvidia container runtime)
FROM ubuntu:24.04

ARG BLENDER_VERSION=5.2.2
ARG BLENDER_SERIES=5.2

ENV DEBIAN_FRONTEND=noninteractive \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=all

# Runtime libraries Blender needs (even in background mode) + ffmpeg for video encoding
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl xz-utils ffmpeg \
        libx11-6 libxi6 libxxf86vm1 libxfixes3 libxrender1 libxext6 libxkbcommon0 \
        libsm6 libice6 libgl1 libegl1 libglu1-mesa libwayland-client0 libwayland-cursor0 \
        libwayland-egl1 libdecor-0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "https://download.blender.org/release/Blender${BLENDER_SERIES}/blender-${BLENDER_VERSION}-linux-x64.tar.xz" \
        | tar -xJ -C /opt \
    && ln -s "/opt/blender-${BLENDER_VERSION}-linux-x64/blender" /usr/local/bin/blender

WORKDIR /work
ENTRYPOINT ["blender"]
CMD ["--version"]
