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
