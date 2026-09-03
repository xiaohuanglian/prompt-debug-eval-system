#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Models module for Virtual Coach

包含各种大语言模型接口的实现。
"""

from .glm_4_air import llm_response as glm_llm_response
from .kedaxunfei_x1 import llm_response as kedaxunfei_llm_response

__all__ = [
    "glm_llm_response",
    "kedaxunfei_llm_response",
]
