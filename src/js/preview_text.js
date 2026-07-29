/**
 * preview_text.js — read-only output preview for comfydv's OUTPUT_NODE=True
 * nodes that return a ComfyUI "ui": {"text": [...]} payload
 * (ChatCompletion, FormatString, RandomChoice).
 *
 * ComfyUI does NOT auto-render an arbitrary node's ui.text — each node type
 * that wants one implements its own onExecuted handler. This mirrors core's
 * own ``PreviewAny`` node (comfy_extras/nodes_preview_any.py +
 * "Comfy.PreviewAny" in the frontend bundle) minus its Markdown/Plaintext
 * toggle, which none of these three nodes need.
 */

import { app } from "../../scripts/app.js";
import { ComfyWidgets } from "../../scripts/widgets.js";

const PREVIEW_NODES = new Set(["ChatCompletion", "FormatString", "RandomChoice"]);

app.registerExtension({
    name: "comfydv.previewText",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!PREVIEW_NODES.has(nodeData.name)) return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);

            const widget = ComfyWidgets.STRING(
                this,
                "comfydv_preview_text",
                ["STRING", { multiline: true }],
                app
            ).widget;
            widget.label = "Preview";
            widget.options.read_only = true;
            // Not a real input — nothing to save/replay in the saved
            // workflow JSON, and read-only anyway.
            widget.options.serialize = false;
            widget.serialize = false;
            widget.inputEl.readOnly = true;

            return result;
        };

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            onExecuted?.apply(this, arguments);

            const widget = this.widgets?.find(w => w.name === "comfydv_preview_text");
            if (!widget) return;

            const text = message?.text ?? "";
            widget.value = Array.isArray(text) ? (text.join("\n\n") ?? "") : text;
            this.setDirtyCanvas(true, true);
        };
    },
});
