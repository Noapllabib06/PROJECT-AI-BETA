import os

file_path = "/home/noapllabib/vllm-311-env/lib/python3.11/site-packages/vllm/transformers_utils/model_arch_config_convertor.py"

with open(file_path, "r") as f:
    content = f.read()

target = """        head_dim = getattr(self.hf_text_config, "head_dim", 0)
        global_head_dim = getattr(self.hf_text_config, "global_head_dim", 0)"""

replacement = """        try:
            head_dim = getattr(self.hf_text_config, "head_dim", 0)
        except Exception:
            head_dim = getattr(self.hf_text_config.per_layer_config[0], "head_dim", 0) if hasattr(self.hf_text_config, "per_layer_config") else 0
        try:
            global_head_dim = getattr(self.hf_text_config, "global_head_dim", 0)
        except Exception:
            global_head_dim = getattr(self.hf_text_config.per_layer_config[0], "global_head_dim", 0) if hasattr(self.hf_text_config, "per_layer_config") else 0"""

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, "w") as f:
        f.write(content)
    print("Patched successfully!")
else:
    print("Target not found.")
