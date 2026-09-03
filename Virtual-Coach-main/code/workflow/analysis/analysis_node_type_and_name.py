from pathlib import Path
import json
import re


input_file = Path(__file__).resolve().parents[1] / "example" / "wf_setup_s03_inter.json"

all_nums = {}

with open(input_file, "r", encoding="utf-8") as f:
    wf_setup = json.load(f)
    for key in wf_setup:
        for node in wf_setup[key]["nodes"]:
            temp_type = node["node_type"]
            temp_type = re.sub(r'\d', 'X', temp_type)

            temp_name = node["node_name"]
            # 将所有数字替换为X
            temp_name = re.sub(r'\d', 'X', temp_name)

            temp_all = "| {:28} | {:28} |".format(temp_type, temp_name)
            
            if temp_all not in all_nums:
                all_nums[temp_all] = 0
            all_nums[temp_all] += 1


print("| {:28} | {:28} | {:5} |".format("Node Type", "Node Name", "Count"))
print("|" + "-"*30 + "|" + "-"*30 + "|" + "-"*7 + "|")
for all_item, count in all_nums.items():
    print(all_item + "{:5} |".format(count))
