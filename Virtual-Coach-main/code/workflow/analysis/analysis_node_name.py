from pathlib import Path
import json


input_file = Path(__file__).resolve().parents[1] / "example" / "wf_setup_s03_inter.json"

name_nums = {}

with open(input_file, "r", encoding="utf-8") as f:
    wf_setup = json.load(f)
    for key in wf_setup:
        for node in wf_setup[key]["nodes"]:
            temp_name = node["node_name"]
            # 将所有数字替换为X
            import re
            temp_name = re.sub(r'\d', 'X', temp_name)
            
            if temp_name not in name_nums:
                name_nums[temp_name] = 0
            name_nums[temp_name] += 1


print("| {:28} | {:5} |".format("Node Name", "Count"))
print("|" + "-"*30 + "|" + "-"*7 + "|")
for node_name, count in name_nums.items():
    print("| {:28} | {:5} |".format(node_name, count))
