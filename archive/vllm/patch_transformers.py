import os

file_path = "/home/noapllabib/vllm-311-env/lib/python3.11/site-packages/transformers/integrations/heterogeneity/configuration_utils.py"

with open(file_path, "r") as f:
    content = f.read()

target = """                if not super().__getattribute__("allow_global_per_layer_attribute_access"):
                    raise AmbiguousGlobalPerLayerAttributeError(
                        f"'{key}' is a per-layer attribute and may vary across layers. Access it via the individual layer "
                        f"configs instead (e.g. config.per_layer_config[i].{key}). To read the global config value from "
                        f"config.{key} anyway, set `allow_global_per_layer_attribute_access` to `True` on the config. "
                        f"Warning: only do this if the caller can safely handle heterogeneous configs; code that assumes "
                        f"a homogeneous model may use the global value incorrectly."
                    )"""

replacement = """                if False:
                    pass"""

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, "w") as f:
        f.write(content)
    print("Transformers patched successfully!")
else:
    print("Target not found.")
