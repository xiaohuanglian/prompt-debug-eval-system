#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Virtual Coach (虚拟教练) - 基于大语言模型的智能虚拟教练交互式课程生成系统

这是一个基于大语言模型的智能虚拟教练系统，旨在为用户提供个性化的交互式课程生成和指导服务。
"""

__version__ = "1.0.0"
__author__ = "Virtual Coach Team"
__email__ = ""
__description__ = "基于大语言模型的智能虚拟教练交互式课程生成系统"

__all__ = [
    "MetadataAgent",
    "glm_llm_response",
    "kedaxunfei_llm_response",
]


def __getattr__(name):
    """懒加载可选入口，避免导入 pipeline 时被 agent/model 依赖拖住。"""
    if name == "MetadataAgent":
        from .agent.MetadataAgent import MetadataAgent
        return MetadataAgent
    if name == "glm_llm_response":
        from .models.glm_4_air import llm_response
        return llm_response
    if name == "kedaxunfei_llm_response":
        from .models.kedaxunfei_x1 import llm_response
        return llm_response
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
