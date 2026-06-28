/**
 * ollama.js — ComfyUI frontend extension for comfydv Ollama nodes.
 *
 * Populates model COMBO widgets on OllamaModelSelector, OllamaLoadModel, and
 * OllamaChatCompletion from a live call to GET /dv/ollama/models?host=<url>.
 */

import { app } from "../../scripts/app.js";

const OLLAMA_COMBO_NODES = new Set([
    "OllamaModelSelector",
    "OllamaLoadModel",
    "OllamaChatCompletion",
]);

/**
 * Fetch model list from the backend and repopulate the COMBO widget.
 * @param {LGraphNode} node
 * @param {string} host - Ollama host URL, e.g. "http://localhost:11434"
 */
async function refreshModelDropdown(node, host) {
    try {
        const resp = await fetch(`/dv/ollama/models?host=${encodeURIComponent(host)}`);
        if (!resp.ok) return;
        const data = await resp.json();
        const models = data.models ?? [];
        if (!models.length) return;

        const modelWidget = node.widgets?.find(w => w.name === "model");
        if (!modelWidget) return;

        const current = modelWidget.value;
        modelWidget.options.values = models;
        modelWidget.value = models.includes(current) ? current : models[0];
        node.setDirtyCanvas(true, false);
    } catch (_) {
        // Ollama unreachable — leave COMBO with server-side defaults
    }
}

/**
 * Locate the host string for a node — either from a connected OllamaClient
 * widget value or from the default.
 */
function getHostFromNode(node) {
    const clientWidget = node.widgets?.find(w => w.name === "host");
    if (clientWidget) return clientWidget.value;
    return "http://localhost:11434";
}

app.registerExtension({
    name: "comfydv.ollama",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!OLLAMA_COMBO_NODES.has(nodeData.name)) return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);

            // Add a refresh button below the model widget
            this.addWidget("button", "⟳ Refresh models", null, () => {
                const host = getHostFromNode(this);
                refreshModelDropdown(this, host);
            });

            // Initial population
            const host = getHostFromNode(this);
            refreshModelDropdown(this, host);

            return result;
        };
    },
});
