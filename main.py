import asyncio
import os
import time
import uuid
from core.knowledge_base import KnowledgeBase
from core.database import CRMDatabase
from core.embeddings import GeminiEmbeddingService
from core.cache import UserHistoryRAG
from core.telemetry import TelemetryLogger
from core.memory import TokenOptimizer
from agent.sales_agent import kayfa_sales_agent, AgentDeps

async def main():
    kb = KnowledgeBase(data_dir="./data/processed")
    db = CRMDatabase()
    deps = AgentDeps(kb=kb, db=db)
    
    mongo_uri = os.getenv("MONGO_URI", "")
    embedding_service = GeminiEmbeddingService()
    
    user_rag = UserHistoryRAG(
        mongo_uri=mongo_uri,
        db_name="kayfa_crm",
        collection_name="user_history",
        embedding_service=embedding_service
    )
    
    telemetry = TelemetryLogger(
        mongo_uri=mongo_uri,
        db_name="kayfa_crm"
    )
    
    print("\n--- KAYFA AI SALES AGENT TERMINAL ---")
    user_id = input("Enter User ID to sign in: ").strip()
    if not user_id:
        user_id = str(uuid.uuid4())
        
    session_id = str(uuid.uuid4())
    message_history = []
    
    session_total_cost = 0.0
    session_total_tokens = 0
    
    while True:
        user_input = input("\nYou: ").strip()
        
        if not user_input:
            continue
            
        if user_input.lower() in ['exit', 'quit']:
            print(f"\nSession Ended. Total Cost: ${session_total_cost:.5f} | Total Tokens: {session_total_tokens}")
            break
            
        start_time = time.time()
        
        past_context = await user_rag.retrieve_user_history(user_input, user_id)
        contextualized_prompt = f"[System Note: The current logged-in user ID is '{user_id}']\n{past_context}\nCurrent Query: {user_input}" if past_context else f"[System Note: The current logged-in user ID is '{user_id}']\nCurrent Query: {user_input}"
        
        result = await kayfa_sales_agent.run(
            contextualized_prompt,
            deps=deps,
            message_history=message_history
        )
        
        latency_ms = (time.time() - start_time) * 1000
        message_history = TokenOptimizer.prune_history(result.all_messages())
        final_response = getattr(result, 'output', getattr(result, 'data', str(result)))
        
        usage = result.usage
        req_tokens = usage.input_tokens if usage else 0
        res_tokens = usage.output_tokens if usage else 0
        _, embed_tokens = await embedding_service.generate_embedding(user_input)
        
        turn_tokens = req_tokens + res_tokens + (embed_tokens * 2)
        session_total_tokens += turn_tokens
        
        turn_cost = ((req_tokens / 1_000_000) * 0.15) + ((res_tokens / 1_000_000) * 0.60) + (((embed_tokens * 2) / 1_000_000) * 0.20)
        session_total_cost += turn_cost
        
        tools_called = []
        print("\n[SYSTEM TRACE START]")
        for msg in result.new_messages():
            if hasattr(msg, 'parts'):
                for part in msg.parts:
                    if part.part_kind == 'tool-call':
                        args = part.args.args_dict if hasattr(part.args, 'args_dict') else str(part.args)
                        tools_called.append({"tool": part.tool_name, "args": args})
                        print(f"TOOL CALL    | Name: {part.tool_name} | Args: {args}")
                    elif part.part_kind == 'tool-return':
                        res_str = str(part.content)
                        if len(res_str) > 150:
                            res_str = res_str[:150] + " ... [TRUNCATED]"
                        print(f"TOOL RETURN  | Name: {part.tool_name} | Result: {res_str}")
                        
        print(f"[SYSTEM TRACE END] Latency: {latency_ms:.2f}ms | Turn Cost: ${turn_cost:.5f} | Session Total: ${session_total_cost:.5f}\n")

        await asyncio.gather(
            user_rag.save_interaction(user_id, user_input, final_response),
            telemetry.log_usage(
                user_id=user_id,
                session_id=session_id,
                prompt=user_input,
                response=final_response,
                input_tokens=req_tokens,
                output_tokens=res_tokens,
                embed_tokens=embed_tokens * 2,
                latency_ms=latency_ms,
                tools_called=tools_called
            )
        )
        
        print(f"Kayfa Agent: {final_response}")

if __name__ == "__main__":
    asyncio.run(main())
