# core/memory.py
from typing import List, Dict, Any

class TokenOptimizer:
    @staticmethod
    def prune_history(message_history: List[Any], max_turns: int = 4) -> List[Any]:
        if len(message_history) <= max_turns * 2:
            return message_history
        return message_history[-(max_turns * 2):]

    @staticmethod
    def compress_tool_output(data: List[Dict[str, Any]], allowed_keys: List[str]) -> List[Dict[str, Any]]:
        return [{k: v for k, v in item.items() if k in allowed_keys} for item in data]

    @staticmethod
    def compress_dict(data: Dict[str, Any], allowed_keys: List[str]) -> Dict[str, Any]:
        if "error" in data:
            return data
        return {k: v for k, v in data.items() if k in allowed_keys}
