// Stolen shamelessly from the excellent Impact Pack
// https://github.com/ltdrdata/ComfyUI-Impact-Pack/blob/971c4a37aa4e77346eaf0ab80adf3972f430bec1/js/impact-pack.js#L413
import { app } from "../../scripts/app.js";

app.registerExtension({
  name: "org.darthveitcher.DynamicNodes",
  async beforeRegisterNodeDef(nodeType, nodeData, app) {
    // console.log("Registering " + nodeData.name);
    if (nodeData.name === "RandomChoice" || nodeData.name === "Random Choice" || nodeData.name === "ToJSON" || nodeData.name === "To JSON") {
      console.log(nodeData.name);
      var input_name = "input";
      switch (nodeData.name) {
        // allows us to update if ever need to grow list
        case "RandomChoice":
          input_name = "input";
          break;
      }
      const onConnectionsChange = nodeType.prototype.onConnectionsChange;
      nodeType.prototype.onConnectionsChange = function (
        type,
        index,
        connected,
        link_info
      ) {
        if (!link_info) return;
        // Find the 'seed' input by its name in the nodeData or node's inputs
        const seedInput = this.inputs.find(input => input.name === "seed");
        if (type == 2) {
          // connect output
          console.log("Connected output.");
          return;
        }
        if (type == 1) {
          console.log("Handling input connection.");
        } else {
          // connect input
          if (
            this.inputs[index].name == "select" ||
            this.inputs[index].name == "sel_mode"
          )
            return;

          if (this.inputs[0].type == "*") {
            const node = app.graph.getNodeById(link_info.origin_id);
            let origin_type = node.outputs[link_info.origin_slot].type;

            if (origin_type == "*") {
              this.disconnectInput(link_info.target_slot);
              return;
            }

            for (let i in this.inputs) {
              let input_i = this.inputs[i];
              if (input_i.name != "select" && input_i.name != "sel_mode")
                input_i.type = origin_type;
            }

            this.outputs[0].type = origin_type;
            this.outputs[0].label = origin_type;
            this.outputs[0].name = origin_type;
          }
        }
        let select_slot = this.inputs.find((x) => x.name == "select");
        let mode_slot = this.inputs.find((x) => x.name == "sel_mode");

        let converted_count = 0;
        converted_count += select_slot ? 1 : 0;
        converted_count += mode_slot ? 1 : 0;
        converted_count += seedInput ? 1 : 0;

        if (!connected && this.inputs.length > 1 + converted_count) {
          const stackTrace = new Error().stack;

          if (
            !stackTrace.includes("LGraphNode.prototype.connect") && // for touch device
            !stackTrace.includes("LGraphNode.connect") && // for mouse device
            !stackTrace.includes("loadGraphData") &&
            this.inputs[index].name != "select" &&
            this.inputs[index].name != "seed"
          ) {
            this.removeInput(index);
          }
        }

        let slot_i = 1;
        let seed_adjust = (seedInput ? 1 : 0)
        let non_seed = this.inputs.length - seed_adjust
        let seed_index = this.inputs.findIndex(item => item.name === 'seed')
        for (let i = 0; i < this.inputs.length; i++) {
          let input_i = this.inputs[i];
            if (input_i.name != "select" && input_i.name != "sel_mode" && input_i.name != "seed") {
            // input_i.name = `${input_name}${slot_i - (slot_i == 1 ? 0 : (non_seed == 2 ? 0 : seed_adjust))}`;
            input_i.name = `${input_name}${Math.min(slot_i, non_seed)}`;
            slot_i++;
          }
          if (input_i.name == "seed") {
            // if (input_i.name != "seed" && connected) {
          }
        }
        if (connected && (index != seed_index) && (this.inputs[index].link != undefined)) {
          // this.addInput(`${input_name}${slot_i - seed_adjust}`, this.outputs[0].type);
          // this.addInput(`${input_name}${slot_i}`, this.outputs[0].type);
          // slot_i++;
        }

        let last_slot = this.inputs[this.inputs.length - 1];
        if (
          (last_slot.name == "select" &&
            last_slot.name != "sel_mode" &&
            this.inputs[this.inputs.length - 2].link != undefined) ||
          (last_slot.name != "select" &&
            last_slot.name != "sel_mode" &&
            last_slot.name != "seed" &&
            last_slot.link != undefined)
        ) {
          if (connected && this.inputs[index].link != undefined) {
            this.addInput(`${input_name}${slot_i}`, this.outputs[0].type);
          }
        }
        if (last_slot.name == "seed" && (this.inputs[this.inputs.length - 2].link != undefined) && (this.name != "seed")) {
          this.addInput(`${input_name}${slot_i}`, this.outputs[0].type);
        }

        if (this.widgets) {
          this.widgets[0].options.max = select_slot
            ? this.inputs.length - 1
            : this.inputs.length;
          this.widgets[0].value = Math.min(
            this.widgets[0].value,
            this.widgets[0].options.max
          );
          if (this.widgets[0].options.max > 0 && this.widgets[0].value == 0)
            this.widgets[0].value = 1;
        }
        var final_seed_index = this.inputs.findIndex(item => item.name === 'seed');
        this.inputs.push(this.inputs.splice(final_seed_index, 1)[0]);
      };
    }
  },
});
