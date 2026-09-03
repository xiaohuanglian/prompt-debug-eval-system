from pathlib import Path
import json


input_file = Path(__file__).resolve().parents[1] / "example" / "wf_setup_s03_inter.json"

typr_nums = {}

with open(input_file, "r", encoding="utf-8") as f:
    wf_setup = json.load(f)
    for key in wf_setup:
        for node in wf_setup[key]["nodes"]:
            if node["node_type"] not in typr_nums:
                typr_nums[node["node_type"]] = 0
            typr_nums[node["node_type"]] += 1


print("| {:28} | {:5} |".format("Node Type", "Count"))
print("|" + "-"*30 + "|" + "-"*7 + "|")
for node_type, count in typr_nums.items():
    print("| {:28} | {:5} |".format(node_type, count))
