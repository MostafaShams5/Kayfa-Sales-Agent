from fastapi import FastAPI
from pydantic import BaseModel
import os
import time
from datetime import datetime, timezone
from core.knowledge_base import KnowledgeBase
from core.database import CRMDatabase
from core.embeddings import GeminiEmbeddingService
from core.cache import UserHistoryRAG, MongoSemanticCache
from core.telemetry import TelemetryLogger
from core.memory import TokenOptimizer
from agent.sales_agent import kayfa_sales_agent, AgentDeps
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Kayfa AI Agent API")

kb = KnowledgeBase(data_dir="./data/processed")
db = CRMDatabase()
deps = AgentDeps(kb=kb, db=db)

mongo_uri = os.getenv("MONGO_URI", "")
embedding_service = GeminiEmbeddingService()
user_rag = UserHistoryRAG(mongo_uri, "kayfa_crm", "user_history", embedding_service)
telemetry = TelemetryLogger(mongo_uri, "kayfa_crm")
semantic_cache = MongoSemanticCache(mongo_uri, "kayfa_crm", "semantic_cache", embedding_service)

class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    prompt: str
    history: list = []

class ChatResponse(BaseModel):
    response: str
    session_id: str
    latency_ms: float
    is_cached: bool
    history: list

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    start_time = time.time()
    
    context_hash = MongoSemanticCache.generate_context_hash(request.history)
    cached_answer = await semantic_cache.get_cached_response(request.prompt, context_hash)
    
    if cached_answer:
        latency_ms = (time.time() - start_time) * 1000
        return ChatResponse(
            response=cached_answer,
            session_id=request.session_id,
            latency_ms=latency_ms,
            is_cached=True,
            history=request.history
        )

    past_context = await user_rag.retrieve_user_history(request.prompt, request.user_id)
    contextualized_prompt = f"[System Note: User ID '{request.user_id}']\n{past_context}\nCurrent Query: {request.prompt}"

    result = await kayfa_sales_agent.run(
        contextualized_prompt,
        deps=deps,
        message_history=request.history
    )

    latency_ms = (time.time() - start_time) * 1000
    pruned_history = TokenOptimizer.prune_history(result.all_messages())
    final_response = getattr(result, 'output', getattr(result, 'data', str(result)))

    usage = result.usage
    req_tokens = usage.input_tokens if usage else 0
    res_tokens = usage.output_tokens if usage else 0
    _, embed_tokens = await embedding_service.generate_embedding(request.prompt)

    tools_called = []
    for msg in result.new_messages():
        if hasattr(msg, 'parts'):
            for part in msg.parts:
                if part.part_kind == 'tool-call':
                    args = part.args.args_dict if hasattr(part.args, 'args_dict') else str(part.args)
                    tools_called.append({"tool": part.tool_name, "args": args, "result": None})
                elif part.part_kind == 'tool-return':
                    for t in reversed(tools_called):
                        if t["tool"] == part.tool_name and t["result"] is None:
                            t["result"] = str(part.content)
                            break

    await user_rag.save_interaction(request.user_id, request.prompt, final_response)
    await semantic_cache.set_cached_response(request.prompt, final_response, context_hash)
    await telemetry.log_usage(
        user_id=request.user_id,
        session_id=request.session_id,
        prompt=request.prompt,
        response=final_response,
        input_tokens=req_tokens,
        output_tokens=res_tokens,
        embed_tokens=embed_tokens * 2,
        latency_ms=latency_ms,
        tools_called=tools_called
    )

    return ChatResponse(
        response=final_response,
        session_id=request.session_id,
        latency_ms=latency_ms,
        is_cached=False,
        history=pruned_history
    )
