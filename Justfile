dev := "docker compose -f docker-compose.yml -f docker-compose.dev.yml"
ci  := "docker compose"

# List available recipes
default:
    @just --list

# Build the base image (run once, or after Dockerfile / ComfyUI version bumps)
build:
    {{dev}} build

# Start ComfyUI with local repo mounted; stays running, streams logs
up:
    {{dev}} up

# Start in the background (detached)
up-d:
    {{dev}} up -d

# Stop and remove containers (keeps the image)
down:
    {{dev}} down

# Tail ComfyUI logs (works whether up or up-d was used)
logs:
    {{dev}} logs -f comfyui

# Open ComfyUI in the browser
open:
    open http://localhost:8188

# Show container health / status
status:
    {{dev}} ps

# Rebuild base image from scratch, clearing Docker cache
rebuild:
    {{dev}} build --no-cache

# CI smoke test — builds from COPY, starts with --quick-test-for-ci, exits
ci-smoke:
    {{ci}} up --build --exit-code-from comfyui

# Regenerate docs/assets/ screenshots from the live ComfyUI dev harness.
# Starts the harness if not already running; leaves it running afterwards.
screenshots:
    @echo "Starting dev harness (no-op if already up)…"
    {{dev}} up -d
    @echo "Waiting for ComfyUI to be healthy…"
    @until docker compose -f docker-compose.yml -f docker-compose.dev.yml ps --format json | python3 -c "import sys,json; s=[c for c in json.load(sys.stdin) if c.get('Name','').endswith('comfyui')]; exit(0 if s and s[0].get('Health')=='healthy' else 1)" 2>/dev/null; do sleep 3; done
    uv run scripts/take_screenshots.py
