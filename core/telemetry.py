from typing import List, Dict, Any
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

class TelemetryLogger:
    def __init__(self, mongo_uri: str, db_name: str):
        self.client = AsyncIOMotorClient(mongo_uri)
        self.collection = self.client[db_name]["usage_logs"]
        self.prices = {
            "groq_input": 0.15,
            "groq_output": 0.60,
            "gemini_embed": 0.20
        }

    async def log_usage(
        self,
        user_id: str,
        session_id: str,
        prompt: str,
        response: str,
        input_tokens: int,
        output_tokens: int,
        embed_tokens: int,
        latency_ms: float,
        tools_called: List[Dict[str, Any]]
    ) -> None:
        cost_groq_in = (input_tokens / 1_000_000) * self.prices["groq_input"]
        cost_groq_out = (output_tokens / 1_000_000) * self.prices["groq_output"]
        cost_embed = (embed_tokens / 1_000_000) * self.prices["gemini_embed"]
        
        doc = {
            "user_id": user_id,
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc),
            "metrics": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "embed_tokens": embed_tokens,
                "latency_ms": latency_ms,
            },
            "cost_usd": {
                "llm_input": cost_groq_in,
                "llm_output": cost_groq_out,
                "embedding": cost_embed,
                "total": cost_groq_in + cost_groq_out + cost_embed
            },
            "behavior": {
                "tools_called": tools_called,
                "prompt_snippet": prompt[:150],
                "response_snippet": response[:150]
            }
        }
        await self.collection.insert_one(doc)
