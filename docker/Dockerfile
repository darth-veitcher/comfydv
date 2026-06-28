FROM python:3.11-slim

WORKDIR /app

# Install system deps needed by ComfyUI
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Clone ComfyUI (pinned tag for reproducibility; bump manually)
ARG COMFYUI_VERSION=v0.3.44
RUN git clone --depth 1 --branch ${COMFYUI_VERSION} \
    https://github.com/comfyanonymous/ComfyUI.git /app/ComfyUI

WORKDIR /app/ComfyUI

# Install ComfyUI deps with CPU-only torch (no CUDA download)
# requests is imported by app/frontend_management.py but not listed in
# ComfyUI's requirements.txt at this tag — pin it explicitly.
RUN pip install --no-cache-dir \
    torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir requests

# Copy comfydv source into custom_nodes
COPY . /app/ComfyUI/custom_nodes/comfydv

# Install comfydv runtime deps
RUN pip install --no-cache-dir \
    -r /app/ComfyUI/custom_nodes/comfydv/requirements.txt

EXPOSE 8188

HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=12 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8188/')"

CMD ["python", "main.py", "--cpu", "--listen", "0.0.0.0", "--port", "8188", "--quick-test-for-ci"]
