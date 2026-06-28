"""
Generate documentation screenshots for comfydv nodes.

Usage:
    uv run scripts/take_screenshots.py

Requires ComfyUI to be running at http://localhost:8188 (use `just up-d` first).
Playwright Chromium must be installed: `uv run playwright install chromium`.
"""

import asyncio
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

COMFYUI_URL = "http://localhost:8188"
OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "assets"
VIEWPORT = {"width": 1400, "height": 860}

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
    h_pad: float = 80,
    v_pad: float = 60,
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
    canvas = page.locator("canvas#graph-canvas, canvas").first
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SCENES = [
    ("fstring.png", scene_format_string_simple),
    ("jinja2.png", scene_format_string_jinja2),
    ("random.png", scene_random_choice),
    ("circuit_breaker.png", scene_circuit_breaker),
]


async def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport=VIEWPORT)
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
