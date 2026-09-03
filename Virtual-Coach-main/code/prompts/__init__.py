#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Prompts module for Virtual Coach

包含各种提示词模板和配置。
"""

from .metadata_agent import (
    ch_to_en_en,
    en_to_ch_en,
    generate_constant_based_on_induction_en,
    generate_cases_by_deduction_en,
    get_answer_en,
    check_answer_en,
    generate_variables_by_analogy_en,
    validate_variables_en,
)

__all__ = [
    "ch_to_en_en",
    "en_to_ch_en", 
    "generate_constant_based_on_induction_en",
    "generate_cases_by_deduction_en",
    "get_answer_en",
    "check_answer_en",
    "generate_variables_by_analogy_en",
    "validate_variables_en",
]
