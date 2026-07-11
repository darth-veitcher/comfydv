/**
 * ollama.js — ComfyUI frontend extension for comfydv's generic LLM nodes.
 *
 * Populates the model widget on LLM nodes from a live call to
 * GET /dv/ollama/models?host=<url>&backend=<ollama|llamacpp>. Despite the
 * file/route name (kept for historical reasons — see MIGRATION_MAP in
 * comfydv.ollama), this now serves both backends: which one a given node's
 * upstream client is determines the `backend` param (see
 * getHostAndBackendFromNode below).
 *
 * LLMModelSelector and LLMLoadModel use a COMBO widget (dropdown).
 * ChatCompletion uses a plain STRING widget (accepts wired values).
 * The Refresh button works the same way for both: it fetches the live list
 * and sets the widget value / updates COMBO options as appropriate.
 */

import { app } from "../../scripts/app.js";

/** Nodes whose model widget is a COMBO dropdown. */
const LLM_COMBO_NODES = new Set(["LLMModelSelector", "LLMLoadModel"]);

/** Nodes whose model widget is a plain STRING (accepts wired input). */
const LLM_STRING_MODEL_NODES = new Set(["ChatCompletion"]);

const LLM_ALL_NODES = new Set([...LLM_COMBO_NODES, ...LLM_STRING_MODEL_NODES]);

/** Registered client node type -> backend param the /dv/ollama/models route expects. */
const CLIENT_NODE_BACKENDS = { OllamaClient: "ollama", LlamaCppClient: "llamacpp" };

/**
 * Fetch model list and update the node's model widget.
 * Works for both COMBO and STRING widgets:
 *   - COMBO: updates options.values + preserves selection if model still exists.
 *   - STRING: sets the value to the first model; keeps existing value if it
 *             still appears in the live list (user may have typed a valid name).
 */
async function refreshModelWidget(node, host, backend) {
    try {
        const resp = await fetch(
            `/dv/ollama/models?host=${encodeURIComponent(host)}&backend=${encodeURIComponent(backend)}`
        );
        if (!resp.ok) return;
        const data = await resp.json();
        const models = data.models ?? [];
        if (!models.length) return;

        const modelWidget = node.widgets?.find(w => w.name === "model");
        if (!modelWidget) return;

        const current = (modelWidget.value ?? "").trim();

        if (Array.isArray(modelWidget.options?.values)) {
            // COMBO widget
            modelWidget.options.values = models;
            modelWidget.value = models.includes(current) ? current : models[0];
        } else {
            // STRING widget — keep current value if it is a known model
            if (!current || !models.includes(current)) {
                modelWidget.value = models[0];
            }
        }

        node.setDirtyCanvas(true, false);
    } catch (_) {
        // Server unreachable — leave widget unchanged
    }
}

/**
 * Locate the host and backend for a node's connected LLM client.
 *
 * Traverses graph links to find a connected OllamaClient or LlamaCppClient
 * node and reads its "host" widget. Falls back to Ollama's default if
 * nothing is wired yet, matching the pre-existing fallback behavior.
 */
function getHostAndBackendFromNode(node) {
    for (const input of node.inputs ?? []) {
        if (!input.link) continue;
        const link = node.graph?.links[input.link];
        if (!link) continue;
        const sourceNode = node.graph?.getNodeById(link.origin_id);
        const backend = sourceNode ? CLIENT_NODE_BACKENDS[sourceNode.type] : undefined;
        if (backend) {
            const hostWidget = sourceNode.widgets?.find(w => w.name === "host");
            if (hostWidget?.value) return { host: hostWidget.value, backend };
        }
    }

    return { host: "http://localhost:11434", backend: "ollama" };
}

app.registerExtension({
    name: "comfydv.ollama",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!LLM_ALL_NODES.has(nodeData.name)) return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);

            const refresh = () => {
                const { host, backend } = getHostAndBackendFromNode(this);
                refreshModelWidget(this, host, backend);
            };

            // Add a Refresh button below the model widget
            this.addWidget("button", "⟳ Refresh models", null, refresh);

            // Initial population on node creation
            refresh();

            return result;
        };
    },
});

/**
 * Live structured-output dynamic sockets for ChatCompletion.
 *
 * Mirrors FormatString's live dynamic-output pattern (see format_string.js):
 * editing structured_output or output_schema posts to a backend route that
 * recomputes ChatCompletion.RETURN_TYPES/RETURN_NAMES (the same
 * update_outputs() path chat() itself uses at execution time) and returns
 * the resulting output list — applied to this node's sockets immediately,
 * so you see the extracted fields appear without having to run the graph
 * first. Backend-agnostic: ChatCompletion is the one generic node both
 * OllamaProvider and LlamaCppProvider feed.
 */
async function updateStructuredOutputs(node, structuredOutput, outputSchema) {
    try {
        const resp = await fetch("/dv/ollama/update_structured_outputs", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                unique_id: String(node.id),
                structured_output: structuredOutput,
                output_schema: outputSchema,
            }),
        });
        if (!resp.ok) return;
        const data = await resp.json();
        applyOutputs(node, data.outputs ?? []);
    } catch (_) {
        // Backend unreachable — leave sockets unchanged.
    }
}

function applyOutputs(node, outputs) {
    node.outputs.length = 0;
    outputs.forEach(o => node.addOutput(o.name, o.type));
    node.setDirtyCanvas(true, true);
    node.graph?.setDirtyCanvas(true, true);
}

app.registerExtension({
    name: "comfydv.ollama.structuredOutput",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "ChatCompletion") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);

            const structuredWidget = this.widgets?.find(w => w.name === "structured_output");
            const schemaWidget = this.widgets?.find(w => w.name === "output_schema");
            if (!structuredWidget || !schemaWidget) return result;

            const update = () =>
                updateStructuredOutputs(this, structuredWidget.value, schemaWidget.value);
            structuredWidget.callback = update;
            schemaWidget.callback = update;

            return result;
        };
    },
});
