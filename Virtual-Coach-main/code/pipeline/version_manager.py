import os
import re
import json
import unicodedata


PROMPT_TEMPLATE_VAR = "PROMPT_TEMPLATE"
SCRATCH_SCENARIO_NAMES = frozenset({"测试", "test", "scratch", "临时测试"})


def normalize_scenario_name(scenario_name: str) -> str:
    """Return the canonical scenario folder name used for version lookup."""
    name = unicodedata.normalize("NFC", scenario_name or "")
    name = "".join(ch for ch in name if unicodedata.category(ch) != "Cf")
    return name.strip()


def is_generic_scratch_scenario_name(scenario_name: str) -> bool:
    """Return True when a scenario name is too generic for a new scratch run."""
    name = normalize_scenario_name(scenario_name)
    return name.lower() in SCRATCH_SCENARIO_NAMES


def build_scratch_scenario_name(note: str, prefix: str = "测试") -> str:
    """Build a concrete scratch scenario name such as 测试_组间总结临时调试."""
    note = normalize_scenario_name(note)
    note = re.sub(r"[\\/:*?\"<>|\s]+", "_", note)
    note = re.sub(r"_+", "_", note).strip("._- ")
    if not note:
        raise ValueError("临时测试场景需要填写具体用途，例如：测试_下一组交互式会话")
    return f"{prefix}_{note}"


class VersionManager:
    """Prompt 版本管理器，管理 data/prompt/{scenario_name}/v{N}.py 文件。"""

    def __init__(self, scenario_name: str):
        self.scenario_name = normalize_scenario_name(scenario_name)
        self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.prompt_dir = os.path.join(self.root_dir, "data", "prompt", self.scenario_name)
        os.makedirs(self.prompt_dir, exist_ok=True)

        # 确保 __init__.py 存在（仅首次构造时检查一次）
        self._init_py_checked = False
        self._ensure_init_py()

    def _ensure_init_py(self):
        """只在首次构造时创建一次 __init__.py，避免重复文件 I/O。"""
        if self._init_py_checked:
            return
        init_path = os.path.join(self.prompt_dir, "__init__.py")
        if not os.path.exists(init_path):
            with open(init_path, "w") as f:
                f.write("")
        self._init_py_checked = True

    @staticmethod
    def _match_version_file(filename: str):
        """匹配 v1.py 与 v1(说明).py 这两类版本文件名。"""
        return re.match(r"v(\d+)(?:\.py|[^0-9].*\.py)$", filename)

    def _resolve_version_file(self, version: int) -> str:
        """优先返回 vN.py；若不存在，兼容 vN(说明).py 等带说明文件。"""
        exact = os.path.join(self.prompt_dir, f"v{version}.py")
        if os.path.exists(exact):
            return exact

        if not os.path.exists(self.prompt_dir):
            return exact

        candidates = []
        for filename in os.listdir(self.prompt_dir):
            m = self._match_version_file(filename)
            if m and int(m.group(1)) == int(version):
                path = os.path.join(self.prompt_dir, filename)
                candidates.append(path)

        if not candidates:
            return exact

        candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return candidates[0]

    def get_current_version(self) -> int:
        """获取当前最高版本号，如果没有版本则返回 0。"""
        versions = []
        if os.path.exists(self.prompt_dir):
            for f in os.listdir(self.prompt_dir):
                m = self._match_version_file(f)
                if m:
                    versions.append(int(m.group(1)))
        return max(versions) if versions else 0

    def save_version(self, prompt_template: str) -> int:
        """
        保存 prompt 为下一个版本。

        参数:
            prompt_template: prompt 模板字符串

        返回:
            int: 保存的版本号
        """
        next_v = self.get_current_version() + 1
        filepath = os.path.join(self.prompt_dir, f"v{next_v}.py")

        # 使用固定安全变量名保存，避免场景名包含中文、空格、连字符时生成非法 Python。
        escaped = prompt_template.replace('"""', '\\"\\"\\"')
        content = f'{PROMPT_TEMPLATE_VAR} = """{escaped}"""\n'

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return next_v

    def load_version(self, version: int) -> str:
        """
        加载指定版本的 prompt 模板。

        参数:
            version: 版本号

        返回:
            str: prompt 模板字符串
        """
        filepath = self._resolve_version_file(version)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"版本文件不存在: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # 优先读取新版固定变量名；回退兼容旧版「场景名 = ...」格式。
        match = re.search(rf'{PROMPT_TEMPLATE_VAR}\s*=\s*"""(.*?)"""', content, re.S)
        if not match:
            match = re.search(r'=\s*"""(.*?)"""', content, re.S)
        if match:
            template = match.group(1)
            # 还原转义的三引号
            return template.replace('\\"\\"\\"', '"""')

        # 尝试单引号
        match = re.search(rf"{PROMPT_TEMPLATE_VAR}\s*=\s*'''(.*?)'''", content, re.S)
        if not match:
            match = re.search(r"=\s*'''(.*?)'''", content, re.S)
        if match:
            return match.group(1)

        raise ValueError(f"无法从 {filepath} 解析 prompt 模板")

    def list_versions(self) -> list:
        """列出所有已保存的版本号。"""
        versions = []
        if os.path.exists(self.prompt_dir):
            for f in os.listdir(self.prompt_dir):
                m = self._match_version_file(f)
                if m:
                    versions.append(int(m.group(1)))
        return sorted(set(versions))

    def save_eval_data(self, eval_data: list):
        """保存评测数据集到 data/eval/{scenario_name}.json。"""
        eval_dir = os.path.join(self.root_dir, "data", "eval")
        os.makedirs(eval_dir, exist_ok=True)
        filepath = os.path.join(eval_dir, f"{self.scenario_name}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(eval_data, f, ensure_ascii=False, indent=2)
        print(f"评测数据已保存: {filepath}")

    def load_eval_data(self) -> list:
        """加载评测数据集。"""
        filepath = os.path.join(self.root_dir, "data", "eval", f"{self.scenario_name}.json")
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"评测数据不存在: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_eval_script(self, script: str):
        """保存评测脚本到 code/eval/eval_prompt_{scenario_name}.py。"""
        eval_dir = os.path.join(self.root_dir, "code", "eval")
        os.makedirs(eval_dir, exist_ok=True)
        filepath = os.path.join(eval_dir, f"eval_prompt_{self.scenario_name}.py")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(script)
        print(f"评测脚本已保存: {filepath}")

    def save_manual_suggestions(self, text: str):
        """保存手动优化建议到 prompt 目录下的 suggestions.txt。"""
        if not text.strip():
            return
        filepath = os.path.join(self.prompt_dir, "suggestions.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"手动建议已保存: {filepath}")

    def load_manual_suggestions(self) -> str:
        """加载之前保存的手动优化建议。"""
        filepath = os.path.join(self.prompt_dir, "suggestions.txt")
        if not os.path.exists(filepath):
            return ""
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    def get_result_path(self, version: int) -> str:
        """获取评测结果文件路径（带时间戳）。"""
        from datetime import datetime
        result_dir = os.path.join(self.root_dir, "data", "eval_result")
        os.makedirs(result_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(
            result_dir,
            f"{self.scenario_name}_v{version}_result_{timestamp}.json"
        )
