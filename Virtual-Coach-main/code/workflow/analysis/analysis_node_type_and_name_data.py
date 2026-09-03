import json
import re

input_file = "/Users/djh/Documents/备份/一般/工作/代码/LLM/github/Virtual-Coach/code/workflow/example/wf_setup_s03_inter.json"
output_file = "analysis_node_type_and_name_data.txt"

all_nums = {}

with open(input_file, "r", encoding="utf-8") as f:
    wf_setup = json.load(f)
    for key in wf_setup:
        for node in wf_setup[key]["nodes"]:
            temp_type = node["node_type"]
            temp_type = re.sub(r'\d', 'X', temp_type)

            temp_name = node["node_name"]
            temp_name = re.sub(r'\d', 'X', temp_name)

            temp_all = "Type: {:} | Name: {:} |".format(temp_type, temp_name)

            if temp_all not in all_nums:
                all_nums[temp_all] = []
            all_nums[temp_all].append(node)
    # 按照key排序
    all_nums = dict(sorted(all_nums.items(), key=lambda x: x[0]))

with open(output_file, "w", encoding="utf-8") as f_out:
    for all_item, nodes in all_nums.items():
        f_out.write(all_item + "\n")
        for node in nodes:
            # json.dumps 确保双引号，确保可以解析
            f_out.write(json.dumps(node, ensure_ascii=False) + "\n")
        f_out.write("-"*10 + "\n")
