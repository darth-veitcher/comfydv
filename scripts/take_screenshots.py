"""
Generate documentation screenshots for comfydv nodes.

Usage:
    uv run scripts/take_screenshots.py

Requires ComfyUI to be running at http://localhost:8188 (use `just up-d` first).
Playwright Chromium must be installed: `uv run playwright install chromium`.
"""

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

COMFYUI_URL = "http://localhost:8188"
OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "assets"
VIEWPORT = {"width": 1400, "height": 860}

# Pre-seed localStorage so ComfyUI loads the canvas directly instead of showing
# the template browser (which appears in fresh sessions without a saved workflow).
_STORAGE_STATE = {
    "cookies": [],
    "origins": [
        {
            "origin": COMFYUI_URL,
            "localStorage": [
                {
                    "name": "workflow",
                    "value": json.dumps(
                        {
                            "last_node_id": 0,
                            "last_link_id": 0,
                            "nodes": [],
                            "links": [],
                            "groups": [],
                            "config": {},
                            "extra": {},
                            "version": 0.4,
                        }
                    ),
                },
                {"name": "Comfy.OpenWorkflowsPaths", "value": "[]"},
                {"name": "Comfy.ActiveWorkflowIndex", "value": "0"},
            ],
        }
    ],
}

# LiteGraph DragAndScale transform: screen = (virtual + offset) * scale
# Place the node at virtual (60, 60) and set offset/scale so it fills the frame nicely.
_VIEW_SCALE = 1.6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _wait_ready(page: Page) -> None:
    """Block until the ComfyUI app object and canvas are initialised."""
    await page.wait_for_function(
        "typeof window.app !== 'undefined' && window.app.graph !== null",
        timeout=30_000,
    )
    # Give extensions time to finish registering
    await asyncio.sleep(3.0)


async def _clear(page: Page) -> None:
    await page.evaluate("window.app.graph.clear(); window.app.canvas.draw(true, true);")
    await asyncio.sleep(0.2)


async def _redraw(page: Page) -> None:
    await page.evaluate(
        "window.app.canvas.setDirty(true, true); window.app.canvas.draw(true, true);"
    )
    await asyncio.sleep(0.3)


async def _frame_node(
    page: Page,
    node_pos: list[float],
    node_size: list[float],
    scale: float = _VIEW_SCALE,
) -> None:
    """Pan/zoom so the node is nicely centred in the viewport."""
    vw = VIEWPORT["width"]
    vh = VIEWPORT["height"]
    node_cx = node_pos[0] + node_size[0] / 2
    node_cy = node_pos[1] + node_size[1] / 2
    # LiteGraph: screen = (virtual + offset) * scale  =>  offset = screen/scale - virtual
    offset_x = vw / 2 / scale - node_cx
    offset_y = vh / 2 / scale - node_cy
    await page.evaluate(
        f"""
        (() => {{
            const c = window.app.canvas;
            c.ds.scale  = {scale};
            c.ds.offset = [{offset_x}, {offset_y}];
            c.draw(true, true);
        }})();
        """
    )
    await asyncio.sleep(0.4)


async def _capture(
    page: Page,
    out: Path,
    node_pos: list[float] | None = None,
    node_size: list[float] | None = None,
    scale: float = _VIEW_SCALE,
    pad: int = 60,
) -> None:
    """Screenshot the canvas, optionally cropped tightly around the node."""
    # ComfyUI's frontend added a minimap canvas since this script was last
    # verified — it appears before #graph-canvas in DOM order, so a bare
    # union selector's `.first` silently grabbed the 250x200 minimap
    # instead of the real graph. Target #graph-canvas explicitly.
    canvas = page.locator("canvas#graph-canvas")
    box = await canvas.bounding_box()
    if box is None:
        await page.screenshot(path=str(out))
    elif node_pos is not None and node_size is not None:
        # Convert virtual node coords → screen coords, then clip with padding.
        # LiteGraph: screen = (virtual + offset) * scale
        offset = await page.evaluate("() => window.app.canvas.ds.offset")
        sx = (node_pos[0] + offset[0]) * scale + box["x"]
        sy = (node_pos[1] + offset[1]) * scale + box["y"]
        sw = node_size[0] * scale
        sh = node_size[1] * scale
        await page.screenshot(
            path=str(out),
            clip={
                "x": max(box["x"], sx - pad),
                "y": max(box["y"], sy - pad),
                "width": min(sw + pad * 2, box["width"]),
                "height": min(sh + pad * 2, box["height"]),
            },
        )
    else:
        await page.screenshot(
            path=str(out),
            clip={
                "x": box["x"],
                "y": box["y"],
                "width": box["width"],
                "height": box["height"],
            },
        )
    print(f"  ✓ {out.relative_to(out.parent.parent.parent)}")


# ---------------------------------------------------------------------------
# Individual node scenes
# ---------------------------------------------------------------------------


async def scene_format_string_simple(page: Page, out: Path) -> None:
    """FormatString — simple Python f-string with two dynamic input sockets."""
    await _clear(page)

    info = await page.evaluate(
        """
        async () => {
            const node = LiteGraph.createNode("FormatString");
            node.pos = [60, 60];
            window.app.graph.add(node);

            const twType = node.widgets.find(w => w.name === "template_type");
            const twTpl  = node.widgets.find(w => w.name === "template");
            if (twType) twType.value = "Simple";
            if (twTpl)  twTpl.value  = "Hello {name}!\\nYou are {age} years old.";

            // Trigger dynamic-input creation via the server round-trip
            if (typeof node.updateNodeConfig === "function") {
                await node.updateNodeConfig();
            }
            await new Promise(r => setTimeout(r, 600));

            window.app.canvas.setDirty(true, true);
            window.app.canvas.draw(true, true);

            return { pos: [node.pos[0], node.pos[1]], size: [node.size[0], node.size[1]] };
        }
        """
    )

    await _frame_node(page, info["pos"], info["size"])
    await _capture(page, out, info["pos"], info["size"])


async def scene_format_string_jinja2(page: Page, out: Path) -> None:
    """FormatString — Jinja2 template showing filters and multiple variables."""
    await _clear(page)

    info = await page.evaluate(
        """
        async () => {
            const node = LiteGraph.createNode("FormatString");
            node.pos = [60, 60];
            window.app.graph.add(node);

            const twType = node.widgets.find(w => w.name === "template_type");
            const twTpl  = node.widgets.find(w => w.name === "template");
            if (twType) twType.value = "Jinja2";
            if (twTpl)  twTpl.value  = "{{ greeting | upper }}, {{ name }}!\\n{{ score }}% → {% if score | int >= 90 %}A{% else %}B{% endif %}";

            if (typeof node.updateNodeConfig === "function") {
                await node.updateNodeConfig();
            }
            await new Promise(r => setTimeout(r, 600));

            window.app.canvas.setDirty(true, true);
            window.app.canvas.draw(true, true);

            return { pos: [node.pos[0], node.pos[1]], size: [node.size[0], node.size[1]] };
        }
        """
    )

    await _frame_node(page, info["pos"], info["size"])
    await _capture(page, out, info["pos"], info["size"])


async def scene_random_choice(page: Page, out: Path) -> None:
    """RandomChoice — three typed inputs and a seed widget."""
    await _clear(page)

    info = await page.evaluate(
        """
        () => {
            const node = LiteGraph.createNode("RandomChoice");
            node.pos = [60, 60];
            window.app.graph.add(node);

            // Seed widget
            const seedWidget = node.widgets.find(w => w.name === "seed");
            if (seedWidget) seedWidget.value = 42;

            // Add extra input slots to demonstrate multi-input capability.
            // RandomChoice starts with one wildcard input; we add two more.
            node.addInput("input2", "*");
            node.addInput("input3", "*");

            window.app.canvas.setDirty(true, true);
            window.app.canvas.draw(true, true);

            return { pos: [node.pos[0], node.pos[1]], size: [node.size[0], node.size[1]] };
        }
        """
    )

    await _frame_node(page, info["pos"], info["size"])
    await _capture(page, out, info["pos"], info["size"])


async def scene_circuit_breaker(page: Page, out: Path) -> None:
    """CircuitBreaker — trigger and status inputs."""
    await _clear(page)

    info = await page.evaluate(
        """
        () => {
            const node = LiteGraph.createNode("CircuitBreaker");
            node.pos = [60, 60];
            window.app.graph.add(node);

            // Set status to false (the interesting case — will interrupt the queue)
            const statusWidget = node.widgets && node.widgets.find(w => w.name === "status");
            if (statusWidget) statusWidget.value = false;

            window.app.canvas.setDirty(true, true);
            window.app.canvas.draw(true, true);

            return { pos: [node.pos[0], node.pos[1]], size: [node.size[0], node.size[1]] };
        }
        """
    )

    await _frame_node(page, info["pos"], info["size"])
    await _capture(page, out, info["pos"], info["size"])


async def scene_ollama_client(page: Page, out: Path) -> None:
    """OllamaClient — single node showing the host URL widget."""
    await _clear(page)

    info = await page.evaluate(
        """
        () => {
            const node = LiteGraph.createNode("OllamaClient");
            node.pos = [60, 60];
            window.app.graph.add(node);
            // Show the default localhost URL that users actually configure
            const hostWidget = node.widgets && node.widgets.find(w => w.name === "host");
            if (hostWidget) hostWidget.value = "http://localhost:11434";
            window.app.canvas.setDirty(true, true);
            window.app.canvas.draw(true, true);
            return { pos: [node.pos[0], node.pos[1]], size: [node.size[0], node.size[1]] };
        }
        """
    )

    await _frame_node(page, info["pos"], info["size"])
    await _capture(page, out, info["pos"], info["size"])


async def scene_ollama_chat(page: Page, out: Path) -> None:
    """ChatCompletion — showing the live model dropdown and prompt widget."""
    await _clear(page)

    info = await page.evaluate(
        """
        async () => {
            const node = LiteGraph.createNode("ChatCompletion");
            node.pos = [60, 60];
            window.app.graph.add(node);

            // Set a demo prompt
            const promptWidget = node.widgets && node.widgets.find(w => w.name === "prompt");
            if (promptWidget) promptWidget.value = "Describe this image in one sentence.";

            // Trigger live model refresh via host.docker.internal
            if (typeof window.__comfydv_refreshModels === "function") {
                await window.__comfydv_refreshModels(node, "http://host.docker.internal:11434");
            } else {
                // Manually fetch and populate the COMBO
                try {
                    const resp = await fetch("/dv/ollama/models?host=http://host.docker.internal:11434&backend=ollama");
                    if (resp.ok) {
                        const data = await resp.json();
                        const models = data.models || [];
                        if (models.length) {
                            const modelWidget = node.widgets && node.widgets.find(w => w.name === "model");
                            if (modelWidget) {
                                modelWidget.options = modelWidget.options || {};
                                modelWidget.options.values = models;
                                modelWidget.value = models[0];
                            }
                        }
                    }
                } catch(e) {}
            }

            await new Promise(r => setTimeout(r, 800));
            window.app.canvas.setDirty(true, true);
            window.app.canvas.draw(true, true);
            return { pos: [node.pos[0], node.pos[1]], size: [node.size[0], node.size[1]] };
        }
        """
    )

    await asyncio.sleep(1.0)
    await _redraw(page)
    await _frame_node(page, info["pos"], info["size"])
    await _capture(page, out, info["pos"], info["size"])


async def scene_structured_output(page: Page, out: Path) -> None:
    """ChatCompletion with structured_output enabled — the live dynamic
    output sockets (summary/sentiment/confidence) that appear as soon as
    output_schema is edited, no graph run required. Exercises the real
    js/ollama.js widget callbacks (structuredWidget.callback /
    schemaWidget.callback), the same code path a live user's checkbox click
    and schema edit trigger — not a hand-simulated approximation."""
    await _clear(page)

    schema = (
        '{"type": "object", "properties": '
        '{"summary": {"type": "string"}, '
        '"sentiment": {"type": "string"}, '
        '"confidence": {"type": "number"}}, '
        '"required": ["summary", "sentiment", "confidence"]}'
    )

    info = await page.evaluate(
        f"""
        async () => {{
            const node = LiteGraph.createNode("ChatCompletion");
            node.pos = [60, 60];
            window.app.graph.add(node);

            const promptWidget = node.widgets.find(w => w.name === "prompt");
            if (promptWidget) promptWidget.value =
                "The new render pipeline cut our export time in half and the team is thrilled.";

            const structuredWidget = node.widgets.find(w => w.name === "structured_output");
            const schemaWidget = node.widgets.find(w => w.name === "output_schema");
            if (structuredWidget) structuredWidget.value = true;
            if (schemaWidget) schemaWidget.value = {json.dumps(schema)};

            // Fire the same callbacks js/ollama.js attaches on node creation —
            // real widget-edit code path, not a re-implementation.
            if (structuredWidget?.callback) await structuredWidget.callback(true);
            if (schemaWidget?.callback) await schemaWidget.callback({json.dumps(schema)});

            await new Promise(r => setTimeout(r, 600));
            window.app.canvas.setDirty(true, true);
            window.app.canvas.draw(true, true);
            return {{ pos: [node.pos[0], node.pos[1]], size: [node.size[0], node.size[1]] }};
        }}
        """
    )

    await asyncio.sleep(0.8)
    await _redraw(page)
    await _frame_node(page, info["pos"], info["size"])
    await _capture(page, out, info["pos"], info["size"])


async def scene_llamacpp_client(page: Page, out: Path) -> None:
    """LlamaCppClient — single node showing the router-mode host URL widget."""
    await _clear(page)

    info = await page.evaluate(
        """
        () => {
            const node = LiteGraph.createNode("LlamaCppClient");
            node.pos = [60, 60];
            window.app.graph.add(node);
            const hostWidget = node.widgets && node.widgets.find(w => w.name === "host");
            if (hostWidget) hostWidget.value = "http://localhost:8080";
            window.app.canvas.setDirty(true, true);
            window.app.canvas.draw(true, true);
            return { pos: [node.pos[0], node.pos[1]], size: [node.size[0], node.size[1]] };
        }
        """
    )

    await _frame_node(page, info["pos"], info["size"])
    await _capture(page, out, info["pos"], info["size"])


async def scene_llamacpp_workflow(page: Page, out: Path) -> None:
    """LlamaCppClient → the same ChatCompletion node the Ollama workflow
    uses, unmodified — the actual point of the adapter pattern. Attempts a
    live model-list refresh via backend=llamacpp against
    host.docker.internal:8080; degrades gracefully (same as a real user's
    "no server running yet" state) if nothing is listening there."""
    await _clear(page)

    info = await page.evaluate(
        """
        async () => {
            const graph = window.app.graph;

            const client = LiteGraph.createNode("LlamaCppClient");
            client.pos = [40, 60];
            graph.add(client);
            const hostWidget = client.widgets.find(w => w.name === "host");
            if (hostWidget) hostWidget.value = "http://host.docker.internal:8080";

            const chat = LiteGraph.createNode("ChatCompletion");
            chat.pos = [380, 40];
            graph.add(chat);
            const promptWidget = chat.widgets.find(w => w.name === "prompt");
            if (promptWidget) promptWidget.value = "Write a haiku about ComfyUI.";

            client.connect(0, chat, 0);

            try {
                const resp = await fetch("/dv/ollama/models?host=http://host.docker.internal:8080&backend=llamacpp");
                if (resp.ok) {
                    const data = await resp.json();
                    const models = data.models || [];
                    if (models.length) {
                        const modelWidget = chat.widgets.find(w => w.name === "model");
                        if (modelWidget) modelWidget.value = models[0];
                    }
                }
            } catch (e) {}

            await new Promise(r => setTimeout(r, 800));
            window.app.canvas.setDirty(true, true);
            window.app.canvas.draw(true, true);

            const nodes = [client, chat];
            const minX = Math.min(...nodes.map(n => n.pos[0])) - 20;
            const minY = Math.min(...nodes.map(n => n.pos[1])) - 20;
            const maxX = Math.max(...nodes.map(n => n.pos[0] + n.size[0])) + 20;
            const maxY = Math.max(...nodes.map(n => n.pos[1] + n.size[1])) + 20;
            return { pos: [minX, minY], size: [maxX - minX, maxY - minY] };
        }
        """
    )

    await asyncio.sleep(1.0)
    await _redraw(page)
    await _frame_node(page, info["pos"], info["size"], scale=1.0)
    await _capture(page, out, info["pos"], info["size"], scale=1.0)


async def scene_ollama_workflow(page: Page, out: Path) -> None:
    """Full mini-workflow: OllamaClient → ChatCompletion + Temperature + Seed options."""
    await _clear(page)

    info = await page.evaluate(
        """
        async () => {
            const graph = window.app.graph;

            // 1. OllamaClient — top-left
            const client = LiteGraph.createNode("OllamaClient");
            client.pos = [40, 40];
            graph.add(client);

            // 2. Temperature option — middle-left
            const temp = LiteGraph.createNode("OllamaOptionTemperature");
            temp.pos = [40, 200];
            graph.add(temp);
            const twTemp = temp.widgets && temp.widgets.find(w => w.name === "temperature");
            if (twTemp) twTemp.value = 0.7;

            // 3. Seed option — below temp
            const seed = LiteGraph.createNode("OllamaOptionSeed");
            seed.pos = [40, 340];
            graph.add(seed);
            const twSeed = seed.widgets && seed.widgets.find(w => w.name === "seed");
            if (twSeed) twSeed.value = 42;

            // 4. ChatCompletion — right
            const chat = LiteGraph.createNode("ChatCompletion");
            chat.pos = [380, 100];
            graph.add(chat);
            const twPrompt = chat.widgets && chat.widgets.find(w => w.name === "prompt");
            if (twPrompt) twPrompt.value = "Write a haiku about ComfyUI.";

            // Set client host to reach host Ollama through Docker
            const hostWidget = client.widgets && client.widgets.find(w => w.name === "host");
            if (hostWidget) hostWidget.value = "http://host.docker.internal:11434";

            // Wire: client.OLLAMA_CLIENT (output 0) → chat.client (input 0)
            client.connect(0, chat, 0);

            // Wire: temp.OLLAMA_OPTIONS (output 0) → seed.options (input 0)
            temp.connect(0, seed, 0);

            // Wire: seed.OLLAMA_OPTIONS (output 0) → chat.options input
            // Find the 'options' input slot index on chat node
            const optSlot = chat.inputs ? chat.inputs.findIndex(inp => inp.name === "options") : 3;
            seed.connect(0, chat, optSlot >= 0 ? optSlot : 3);

            // Refresh model dropdowns for chat node
            try {
                const resp = await fetch("/dv/ollama/models?host=http://host.docker.internal:11434&backend=ollama");
                if (resp.ok) {
                    const data = await resp.json();
                    const models = data.models || [];
                    if (models.length) {
                        const modelWidget = chat.widgets && chat.widgets.find(w => w.name === "model");
                        if (modelWidget) {
                            modelWidget.options = modelWidget.options || {};
                            modelWidget.options.values = models;
                            modelWidget.value = models[0];
                        }
                    }
                }
            } catch(e) {}

            await new Promise(r => setTimeout(r, 1200));
            window.app.canvas.setDirty(true, true);
            window.app.canvas.draw(true, true);

            // Bounding box across all 4 nodes
            const nodes = [client, temp, seed, chat];
            const minX = Math.min(...nodes.map(n => n.pos[0])) - 20;
            const minY = Math.min(...nodes.map(n => n.pos[1])) - 20;
            const maxX = Math.max(...nodes.map(n => n.pos[0] + n.size[0])) + 20;
            const maxY = Math.max(...nodes.map(n => n.pos[1] + n.size[1])) + 20;
            return {
                pos: [minX, minY],
                size: [maxX - minX, maxY - minY],
            };
        }
        """
    )

    # Wait for model dropdowns to refresh via /dv/ollama/models
    await asyncio.sleep(2.5)
    await _redraw(page)
    await _frame_node(page, info["pos"], info["size"], scale=1.0)
    await _capture(page, out, info["pos"], info["size"], scale=1.0)


async def scene_ollama_lifecycle(page: Page, out: Path) -> None:
    """Full load → chat → unload chain showing the pass-through pattern."""
    await _clear(page)

    info = await page.evaluate(
        """
        async () => {
            const graph = window.app.graph;

            // OllamaClient — far left, vertically centred relative to the chain
            const client = LiteGraph.createNode("OllamaClient");
            client.pos = [60, 300];
            graph.add(client);
            const hostWidget = client.widgets && client.widgets.find(w => w.name === "host");
            if (hostWidget) hostWidget.value = "http://localhost:11434";

            // OllamaLoadModel — generous gap right of client
            const load = LiteGraph.createNode("LLMLoadModel");
            load.pos = [380, 80];
            graph.add(load);

            // OllamaChatCompletion — wide node, plenty of space to the right of load
            const chat = LiteGraph.createNode("ChatCompletion");
            chat.pos = [720, 40];
            graph.add(chat);
            const twPrompt = chat.widgets && chat.widgets.find(w => w.name === "prompt");
            if (twPrompt) twPrompt.value = "Describe this image in one sentence.";

            // OllamaUnloadModel — far right, vertically offset to match chat's outputs
            const unload = LiteGraph.createNode("LLMUnloadModel");
            unload.pos = [1200, 280];
            graph.add(unload);

            // Populate model dropdowns from live Ollama
            try {
                const resp = await fetch("/dv/ollama/models?host=http://host.docker.internal:11434&backend=ollama");
                if (resp.ok) {
                    const data = await resp.json();
                    const models = data.models || [];
                    if (models.length) {
                        for (const n of [load, chat]) {
                            const w = n.widgets && n.widgets.find(w => w.name === "model");
                            if (w) { w.options = w.options || {}; w.options.values = models; w.value = models[0]; }
                        }
                    }
                }
            } catch(e) {}

            // Wire: client → load, chat, unload
            client.connect(0, load, 0);
            client.connect(0, chat, 0);
            client.connect(0, unload, 0);

            // Wire: load.model_name → chat.model_name (forces Load before Chat)
            const chatModelNameSlot = chat.inputs
                ? chat.inputs.findIndex(i => i.name === "model_name")
                : -1;
            if (chatModelNameSlot >= 0) load.connect(0, chat, chatModelNameSlot);

            // Wire: chat.model_name (output 2) → unload.model
            // Wire: chat.response (output 0) → unload.passthrough
            const unloadModelSlot = unload.inputs
                ? unload.inputs.findIndex(i => i.name === "model")
                : 1;
            const unloadPassSlot = unload.inputs
                ? unload.inputs.findIndex(i => i.name === "passthrough")
                : -1;
            chat.connect(2, unload, unloadModelSlot >= 0 ? unloadModelSlot : 1);
            if (unloadPassSlot >= 0) chat.connect(0, unload, unloadPassSlot);

            // Let nodes render and auto-size before reading bounding box
            await new Promise(r => setTimeout(r, 1500));
            window.app.canvas.setDirty(true, true);
            window.app.canvas.draw(true, true);
            await new Promise(r => setTimeout(r, 300));

            const nodes = [client, load, chat, unload];
            const minX = Math.min(...nodes.map(n => n.pos[0])) - 30;
            const minY = Math.min(...nodes.map(n => n.pos[1])) - 30;
            const maxX = Math.max(...nodes.map(n => n.pos[0] + n.size[0])) + 30;
            const maxY = Math.max(...nodes.map(n => n.pos[1] + n.size[1])) + 30;
            return { pos: [minX, minY], size: [maxX - minX, maxY - minY] };
        }
        """
    )

    await asyncio.sleep(1.5)
    await _redraw(page)
    await _frame_node(page, info["pos"], info["size"], scale=0.72)
    await _capture(page, out, info["pos"], info["size"], scale=0.72)


async def scene_ollama_options(page: Page, out: Path) -> None:
    """OllamaOption nodes — Temperature, Seed, MaxTokens in a vertical chain."""
    await _clear(page)

    info = await page.evaluate(
        """
        () => {
            const graph = window.app.graph;

            const temp = LiteGraph.createNode("OllamaOptionTemperature");
            temp.pos = [60, 40];
            graph.add(temp);
            const twTemp = temp.widgets && temp.widgets.find(w => w.name === "temperature");
            if (twTemp) twTemp.value = 0.8;

            const seed = LiteGraph.createNode("OllamaOptionSeed");
            seed.pos = [60, 180];
            graph.add(seed);
            const twSeed = seed.widgets && seed.widgets.find(w => w.name === "seed");
            if (twSeed) twSeed.value = 1337;

            const maxTok = LiteGraph.createNode("OllamaOptionMaxTokens");
            maxTok.pos = [60, 320];
            graph.add(maxTok);
            const twMax = maxTok.widgets && maxTok.widgets.find(w => w.name === "max_tokens");
            if (twMax) twMax.value = 256;

            // Chain: temp → seed → maxTok (node.connect(outputSlot, targetNode, inputSlot))
            temp.connect(0, seed, 0);
            seed.connect(0, maxTok, 0);

            window.app.canvas.setDirty(true, true);
            window.app.canvas.draw(true, true);

            const nodes = [temp, seed, maxTok];
            const minX = Math.min(...nodes.map(n => n.pos[0])) - 20;
            const minY = Math.min(...nodes.map(n => n.pos[1])) - 20;
            const maxX = Math.max(...nodes.map(n => n.pos[0] + n.size[0])) + 20;
            const maxY = Math.max(...nodes.map(n => n.pos[1] + n.size[1])) + 20;
            return { pos: [minX, minY], size: [maxX - minX, maxY - minY] };
        }
        """
    )

    await _frame_node(page, info["pos"], info["size"], scale=1.2)
    await _capture(page, out, info["pos"], info["size"], scale=1.2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SCENES = [
    ("fstring.png", scene_format_string_simple),
    ("jinja2.png", scene_format_string_jinja2),
    ("random.png", scene_random_choice),
    ("circuit_breaker.png", scene_circuit_breaker),
    # Ollama nodes (spec 006)
    ("ollama_client.png", scene_ollama_client),
    ("ollama_chat.png", scene_ollama_chat),
    ("ollama_workflow.png", scene_ollama_workflow),
    ("ollama_options.png", scene_ollama_options),
    ("ollama_lifecycle.png", scene_ollama_lifecycle),
    # Structured output (ADR-007 / pydantic-ai)
    ("structured_output.png", scene_structured_output),
    # llama.cpp (spec 008)
    ("llamacpp_client.png", scene_llamacpp_client),
    ("llamacpp_workflow.png", scene_llamacpp_workflow),
]


async def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport=VIEWPORT, storage_state=_STORAGE_STATE
        )
        page = await context.new_page()

        print(f"Opening {COMFYUI_URL} …")
        try:
            await page.goto(COMFYUI_URL, wait_until="networkidle", timeout=20_000)
        except Exception as exc:
            print(f"ERROR: Could not reach {COMFYUI_URL}: {exc}")
            print("Is the ComfyUI harness running?  Run: just up-d")
            return 1

        print("Waiting for ComfyUI to initialise …")
        await _wait_ready(page)

        print("Taking screenshots:")
        for filename, scene_fn in SCENES:
            out_path = OUTPUT_DIR / filename
            await scene_fn(page, out_path)

        await browser.close()

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
