try:
    from .default_config import default_knewledge
except ImportError:
    from default_config import default_knewledge

class Retriever:
    def __init__(self, knewledge: dict = default_knewledge):
        self.knewledge = knewledge

    def get_knowledge_first_level_key(self) -> list:
        return list(self.knewledge.keys())
    
    def get_knowledge_second_level_key(self, first_level_key: str) -> list:
        return list(self.knewledge[first_level_key].keys()) 

    def get_knowledge_content(self, first_level_key: str, second_level_key: str) -> str:
        first_level_keys = self.get_knowledge_first_level_key()
        if first_level_key not in first_level_keys:
            return f"【{first_level_key}】不存在, 存在的一级键有: {first_level_keys}"
        
        second_level_keys = self.get_knowledge_second_level_key(first_level_key)
        if second_level_key not in second_level_keys:
            second_level_key_all = []
            for second_level_key_item in second_level_keys:
                temp = f"【{first_level_key}.{second_level_key_item}】"
                second_level_key_all.append(temp)
            return f"【{first_level_key}.{second_level_key}】不存在,存在的二级键有: {second_level_key_all}"

        file_path = self.knewledge[first_level_key][second_level_key]
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    
    def get_base_knowledge_content(self) -> str:
        return self.get_knowledge_content("base", "base")
    
    def get_test_input_knowledge_content(self) -> str:
        return self.get_knowledge_content("base", "test_input")

if __name__ == "__main__":
    retriever = Retriever()
    # print(retriever.get_knowledge_first_level_key())
    # print(retriever.get_knowledge_second_level_key("workflow"))
    # print(retriever.get_knowledge_content("workflow", "base"))
    print(retriever.get_base_knowledge_content())