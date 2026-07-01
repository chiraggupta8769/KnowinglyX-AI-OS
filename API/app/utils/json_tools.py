"""
json_tools — safely extract and parse JSON from LLM responses
that may wrap output in markdown code fences.
"""
from __future__ import annotations

import json
import re


def extract_json(text: str) -> str:
    """
    Strip markdown code fences and extract the raw JSON string.
    Handles: ```json ... ```, ``` ... ```, or bare JSON.
    """
    # Remove ```json ... ``` or ``` ... ``` fences
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        return fence_match.group(1).strip()
    return text


def parse_llm_json(text: str) -> dict | list:
    """
    Parse JSON from an LLM response, stripping markdown fences first.
    Raises json.JSONDecodeError if parsing fails after cleanup.
    """
    clean = extract_json(text)
    return json.loads(clean)
