import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "org.darthveitcher.FormatString",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "FormatString") {
            console.log("FormatString extension is being registered");

            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                console.log("FormatString instance created");
                const result = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
                
                this.formatStringNodeId = `format_string_${this.id}`;
                console.log(`Assigned ID: ${this.formatStringNodeId}`);
                
                const templateTypeWidget = this.widgets.find(w => w.name === "template_type");
                const templateWidget = this.widgets.find(w => w.name === "template");
                
                if (templateTypeWidget && templateWidget) {
                    console.log("Template widgets found, adding callbacks");
                    templateTypeWidget.callback = () => this.updateNodeConfig();
                    templateWidget.callback = () => this.updateNodeConfig();
                } else {
                    console.log("Template widgets not found");
                }
                
                // Add load button
                this.addWidget("button", "Load", "load", () => {
                    this.loadNodeState();
                });
                
                return result;
            };

            nodeType.prototype.updateNodeConfig = async function () {
                const templateType = this.widgets.find(w => w.name === "template_type").value;
                const template = this.widgets.find(w => w.name === "template").value;
                console.log(`Updating node config for ${this.formatStringNodeId}`);
                try {
                    const response = await fetch('/update_format_string_node', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ 
                            nodeId: this.formatStringNodeId,
                            template_type: templateType,
                            template: template 
                        })
                    });
                    
                    if (response.status === 200) {
                        const data = await response.json();
                        console.log("Received updated config:", data);
                        
                        this.updateInputsAndOutputs(data);
                    } else {
                        console.error('Failed to update node configuration:', await response.text());
                    }
                } catch (error) {
                    console.error('Error updating node configuration:', error);
                }
            };

            nodeType.prototype.updateInputsAndOutputs = function(config) {
                // Update inputs
                const dynamicInputs = Object.keys(config.inputs).filter(key => 
                    !["template_type", "template", "save_path"].includes(key)
                );

                // Remove obsolete inputs
                this.inputs = this.inputs.filter(input => {
                    const keep = ["template_type", "template", "save_path"].includes(input.name) || dynamicInputs.includes(input.name);
                    if (!keep) console.log(`Removing input: ${input.name}`);
                    return keep;
                });

                // Add new inputs in the correct order
                dynamicInputs.forEach(key => {
                    if (!this.inputs.find(input => input.name === key)) {
                        console.log(`Adding new input: ${key}`);
                        this.addInput(key, "STRING");
                    }
                });
                
                // Update outputs
                console.log(`Updating outputs: ${config.outputs.length}`);
                this.outputs.length = 0;  // Clear existing outputs
                config.outputs.forEach(output => {
                    this.addOutput(output.name, output.type);
                });
                
                // Trigger a node size recalculation
                this.setDirtyCanvas(true, true);
                this.graph.setDirtyCanvas(true, true);
            };

            nodeType.prototype.loadNodeState = async function () {
                let savePath = this.getSavePathValue();

                if (!savePath) {
                    alert("Please specify a save_path in the widget or ensure it's connected as an input before loading.");
                    return;
                }

                try {
                    const response = await fetch('/load_format_string_node', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ file_path: savePath })
                    });
                    if (response.status === 200) {
                        const state = await response.json();
                        if (Object.keys(state).length > 0) {
                            // Update template type and template
                            this.widgets.find(w => w.name === "template_type").value = state.template_type;
                            this.widgets.find(w => w.name === "template").value = state.template;
                            
                            // Update inputs
                            for (const [key, value] of Object.entries(state.inputs)) {
                                if (!this.inputs.find(input => input.name === key)) {
                                    this.addInput(key, "STRING");
                                }
                            }
                            
                            await this.updateNodeConfig();
                            alert("Node state loaded successfully!");
                        } else {
                            alert("No saved state found in the specified file.");
                        }
                    } else {
                        alert("Error loading node state.");
                    }
                } catch (error) {
                    console.error('Error loading node state:', error);
                    alert("Error loading node state.");
                }
            };

            // Helper method to get save_path value
            nodeType.prototype.getSavePathValue = function() {
                const savePathWidget = this.widgets.find(w => w.name === "save_path");
                const savePathInput = this.inputs.find(w => w.name === "save_path");
                if (savePathInput && savePathInput.link != null) {
                    console.log(savePathInput);
                    // If savePath is empty, it might be because it's connected as an input
                    // We can't access the input value directly here, so we'll need to handle this case differently
                }
                console.log("savePathWidget: " + savePathWidget.value);
                return savePathWidget ? savePathWidget.value : null;
            };

            // Override the original execute method
            const originalExecute = nodeType.prototype.onExecute;
            nodeType.prototype.onExecute = function(inputs) {
                // If save_path is provided as an input, update the widget
                if (inputs.save_path !== undefined) {
                    const savePathWidget = this.widgets.find(w => w.name === "save_path");
                    if (savePathWidget) {
                        savePathWidget.value = inputs.save_path;
                    }
                }

                // Ensure save_path is included in the inputs
                inputs.save_path = this.getSavePathValue();

                // Call the original execute method
                originalExecute.call(this, inputs);
            };
        }
    }
});

console.log("FormatString extension script loaded");