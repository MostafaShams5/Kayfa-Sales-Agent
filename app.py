import streamlit as st
import asyncio
import os
import pandas as pd
import uuid
import base64
from datetime import datetime, timezone
from core.auth import AuthManager
from core.analytics import CostAnalytics
from core.knowledge_base import KnowledgeBase
from core.database import CRMDatabase
from core.embeddings import GeminiEmbeddingService
from core.cache import UserHistoryRAG, MongoSemanticCache
from core.telemetry import TelemetryLogger
from core.memory import TokenOptimizer
from agent.sales_agent import kayfa_sales_agent, AgentDeps
from motor.motor_asyncio import AsyncIOMotorClient

import streamlit as st
import os
from dotenv import load_dotenv

# 1. Load local .env file if it exists (for local testing)
load_dotenv()

# 2. Force Streamlit Cloud secrets into the OS environment (for production)
try:
    if "GROQ_API_KEY" in st.secrets:
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
    if "GEMINI_API_KEY" in st.secrets:
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
    if "MONGO_URI" in st.secrets:
        os.environ["MONGO_URI"] = st.secrets["MONGO_URI"]
except FileNotFoundError:
    pass # Ignore if there is no secrets file (local environment)

st.set_page_config(page_title="Kayfa AI | Sales Agent", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
        .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
            padding-left: 1rem;
            padding-right: 1rem;
            max-width: 100%;
        }
        .rtl-text {
            direction: rtl;
            text-align: right;
            font-family: 'Arial', sans-serif;
        }
        .stChatMessage {
            direction: rtl;
        }
        div[data-testid="stChatInput"] textarea {
            direction: rtl;
            text-align: right;
        }
        div[data-testid="stChatInput"] {
            direction: rtl;
        }
    </style>
""", unsafe_allow_html=True)

try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

if loop.is_closed():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

def run_async(coroutine):
    return loop.run_until_complete(coroutine)

@st.cache_resource
def load_knowledge_base():
    return KnowledgeBase(data_dir="./data/processed")

def init_backend():
    mongo_uri = os.getenv("MONGO_URI", "")
    kb = load_knowledge_base()
    db = CRMDatabase()
    deps = AgentDeps(kb=kb, db=db)
    
    auth = AuthManager(mongo_uri=mongo_uri, db_name="kayfa_crm")
    analytics = CostAnalytics(mongo_uri=mongo_uri, db_name="kayfa_crm")
    embedding_service = GeminiEmbeddingService()
    user_rag = UserHistoryRAG(mongo_uri=mongo_uri, db_name="kayfa_crm", collection_name="user_history", embedding_service=embedding_service)
    telemetry = TelemetryLogger(mongo_uri=mongo_uri, db_name="kayfa_crm")
    
    client = AsyncIOMotorClient(mongo_uri)
    raw_db = client["kayfa_crm"]
    
    return deps, auth, analytics, user_rag, telemetry, embedding_service, raw_db

deps, auth, analytics, user_rag, telemetry, embedding_service, raw_db = init_backend()

if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "role" not in st.session_state:
    st.session_state.role = None
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent_history" not in st.session_state:
    st.session_state.agent_history = []

def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return None

def render_welcome_banner():
    logo_b64 = None
    mime_type = "image/svg+xml"
    if os.path.exists("Kayfa.svg"):
        logo_b64 = get_base64_image("Kayfa.svg")
    elif os.path.exists("Kayfa.png"):
        logo_b64 = get_base64_image("Kayfa.png")
        mime_type = "image/png"
        
    img_html = f'<img src="data:{mime_type};base64,{logo_b64}" width="140" style="display:block; margin-left:auto;">' if logo_b64 else '<h2 style="color:#3B82F6; text-align:right; margin:0;">Kayfa</h2>'
    
    st.markdown(f"""
        <div style="background: #FFFFFF; border: 1px solid #BFDBFE; border-radius: 12px; padding: 32px; margin-bottom: 24px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
            <table style="width:100%; border:none; border-collapse:collapse; background:transparent;">
                <tr style="background:transparent; border:none;">
                    <td style="width:80%; vertical-align:middle; border:none; padding:0;">
                        <h2 style="color: #1E3A8A; margin: 0 0 12px 0; font-family: 'Arial', sans-serif; font-size: 26px; font-weight: 700;">Kayfa AI Sales Agent</h2>
                        <p style="color: #334155; margin: 0; font-size: 16px; line-height: 1.6; font-family: 'Arial', sans-serif;">
                            Welcome to the Kayfa interactive chat assistant. This conversational agent talks with potential learners in both Arabic and English, recommends the right courses and roadmaps from our knowledge base, answers operation policies, and securely captures qualified customer leads directly into the team CRM.
                        </p>
                    </td>
                    <td style="width:20%; vertical-align:middle; text-align:right; border:none; padding:0 0 0 24px;">
                        {img_html}
                    </td>
                </tr>
            </table>
        </div>
    """, unsafe_allow_html=True)

def render_sidebar_logo():
    logo_b64 = None
    mime_type = "image/svg+xml"
    if os.path.exists("Kayfa.svg"):
        logo_b64 = get_base64_image("Kayfa.svg")
    elif os.path.exists("Kayfa.png"):
        logo_b64 = get_base64_image("Kayfa.png")
        mime_type = "image/png"
        
    if logo_b64:
        st.sidebar.markdown(f'<img src="data:{mime_type};base64,{logo_b64}" width="120" style="display:block; margin-bottom: 20px;">', unsafe_allow_html=True)
    else:
        st.sidebar.markdown("<h3 style='color: #3B82F6; margin-bottom: 20px;'>Kayfa</h3>", unsafe_allow_html=True)

def page_auth():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.write("")
        st.write("")
        st.title("Kayfa Platform")
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            l_user = st.text_input("Username", key="l_user")
            l_pass = st.text_input("Password", type="password", key="l_pass")
            if st.button("Login", use_container_width=True):
                try:
                    uid, sid = run_async(auth.login(l_user, l_pass))
                    st.session_state.user_id = uid
                    st.session_state.session_id = sid
                    st.session_state.role = "admin" if l_user.lower() == "admin" else "user"
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
                    
        with tab2:
            r_user = st.text_input("Username", key="r_user")
            r_pass = st.text_input("Password", type="password", key="r_pass")
            if st.button("Register", use_container_width=True):
                try:
                    run_async(auth.register(r_user, r_pass))
                    st.success("Registered! Please login.")
                except Exception as e:
                    st.error(str(e))

def page_chat():
    with st.sidebar:
        render_sidebar_logo()
        st.markdown("### Profile Navigation")
        
        past_sessions = run_async(raw_db["usage_logs"].distinct("session_id", {"user_id": st.session_state.user_id}))
        session_options = ["Current Session"] + past_sessions
        selected_session = st.selectbox("Select Conversation History", session_options, index=0)
        
        if selected_session != "Current Session" and st.session_state.session_id != selected_session:
            st.session_state.session_id = selected_session
            past_logs = run_async(raw_db["usage_logs"].find({"session_id": selected_session}).sort("timestamp", 1).to_list(length=100))
            st.session_state.messages = []
            for log in past_logs:
                st.session_state.messages.append({"role": "user", "content": log["behavior"]["prompt_snippet"]})
                st.session_state.messages.append({"role": "assistant", "content": log["behavior"]["response_snippet"]})
            st.session_state.agent_history = []

        if st.button("Start New Conversation", use_container_width=True):
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.session_state.agent_history = []
            st.rerun()

        st.write("")
        if st.button("Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    render_welcome_banner()
    st.divider()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(f"<div class='rtl-text'>{msg['content']}</div>", unsafe_allow_html=True)

    if prompt := st.chat_input("اكتب رسالتك هنا..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(f"<div class='rtl-text'>{prompt}</div>", unsafe_allow_html=True)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("<div class='rtl-text'>...</div>", unsafe_allow_html=True)
            
            start_time = datetime.now()
            
            context_hash = MongoSemanticCache.generate_context_hash(st.session_state.agent_history)
            semantic_cache = MongoSemanticCache(
                mongo_uri=os.getenv("MONGO_URI", ""),
                db_name="kayfa_crm",
                collection_name="semantic_cache",
                embedding_service=embedding_service
            )
            cached_answer = run_async(semantic_cache.get_cached_response(prompt, context_hash))
            
            if cached_answer:
                latency_ms = (datetime.now() - start_time).total_seconds() * 1000
                placeholder.markdown(f"<div class='rtl-text'>{cached_answer}</div>", unsafe_allow_html=True)
                st.session_state.messages.append({"role": "assistant", "content": cached_answer})
                
                doc = {
                    "user_id": st.session_state.user_id,
                    "session_id": st.session_state.session_id,
                    "timestamp": datetime.now(timezone.utc),
                    "is_cache_hit": True,
                    "metrics": {"input_tokens": 0, "output_tokens": 0, "embed_tokens": 0, "latency_ms": latency_ms},
                    "cost_usd": {"llm_input": 0.0, "llm_output": 0.0, "embedding": 0.0, "total": 0.0},
                    "behavior": {
                        "tools_called": [{"tool": "Semantic Cache Lookup", "args": "Match Verified Threshold Cosine"}],
                        "prompt_snippet": prompt,
                        "response_snippet": cached_answer
                    }
                }
                run_async(raw_db["usage_logs"].insert_one(doc))
            else:
                past_context = run_async(user_rag.retrieve_user_history(prompt, st.session_state.user_id))
                contextualized_prompt = f"[System Note: User ID '{st.session_state.user_id}']\n{past_context}\nCurrent Query: {prompt}"
                
                result = run_async(kayfa_sales_agent.run(
                    contextualized_prompt,
                    deps=deps,
                    message_history=st.session_state.agent_history
                ))
                
                latency_ms = (datetime.now() - start_time).total_seconds() * 1000
                st.session_state.agent_history = TokenOptimizer.prune_history(result.all_messages())
                final_response = getattr(result, 'output', getattr(result, 'data', str(result)))
                
                placeholder.markdown(f"<div class='rtl-text'>{final_response}</div>", unsafe_allow_html=True)
                st.session_state.messages.append({"role": "assistant", "content": final_response})
                
                usage = result.usage
                req_tokens = usage.input_tokens if usage else 0
                res_tokens = usage.output_tokens if usage else 0
                _, embed_tokens = run_async(embedding_service.generate_embedding(prompt))
                
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

                run_async(user_rag.save_interaction(st.session_state.user_id, prompt, final_response))
                run_async(semantic_cache.set_cached_response(prompt, final_response, context_hash))
                run_async(telemetry.log_usage(
                    user_id=st.session_state.user_id,
                    session_id=st.session_state.session_id,
                    prompt=prompt,
                    response=final_response,
                    input_tokens=req_tokens,
                    output_tokens=res_tokens,
                    embed_tokens=embed_tokens * 2,
                    latency_ms=latency_ms,
                    tools_called=tools_called
                ))

def page_admin_trace():
    render_welcome_banner()
    st.title("Behavior & Trace Monitor (Monitor B)")
    
    users = run_async(raw_db["users"].find().to_list(length=100))
    if not users:
        st.warning("No telemetry profiles isolated.")
        return
        
    tabs = st.tabs([u["username"] for u in users])
    
    for idx, user in enumerate(users):
        with tabs[idx]:
            logs = run_async(raw_db["usage_logs"].find({"user_id": user["user_id"]}).sort("timestamp", -1).to_list(length=1000))
            if not logs:
                st.info("No recorded context transitions for this identifier.")
                continue
                
            user_total_cost = sum(log.get("cost_usd", {}).get("total", 0.0) for log in logs)
            st.markdown(f"#### Total User Cost: ${user_total_cost:.5f}")
            
            sessions = {}
            for log in logs:
                sid = log.get("session_id", "Unknown")
                if sid not in sessions:
                    sessions[sid] = []
                sessions[sid].append(log)
                
            for sid, session_logs in sessions.items():
                session_cost = sum(l.get("cost_usd", {}).get("total", 0.0) for l in session_logs)
                with st.expander(f"Session: {sid} | Cost: ${session_cost:.5f} | Messages: {len(session_logs)}"):
                    for log in session_logs:
                        is_hit = log.get("is_cache_hit", False)
                        title_label = f"⚡ SEMANTIC CACHE HIT | {log['timestamp']}" if is_hit else f"Inference Roundtrip | {log['timestamp']}"
                        
                        st.markdown(f"**{title_label} | Msg Cost: ${log['cost_usd']['total']:.5f}**")
                        st.markdown(f"**User Prompt:** <div class='rtl-text'>{log['behavior']['prompt_snippet']}</div>", unsafe_allow_html=True)
                        st.markdown(f"**Agent Generation:** <div class='rtl-text'>{log['behavior']['response_snippet']}</div>", unsafe_allow_html=True)
                        
                        tools = log['behavior'].get('tools_called', [])
                        if tools:
                            for t in tools:
                                st.markdown(f"- **Tool:** `{t.get('tool')}`")
                                st.markdown(f"  - **Args:** `{t.get('args')}`")
                                if t.get('result'):
                                    st.markdown(f"  - **Output:** `{str(t.get('result'))[:400]}`")
                                    
                        st.caption(f"Latency: {log['metrics']['latency_ms']:.2f}ms | Tokens (In / Out / Embed): {log['metrics']['input_tokens']} / {log['metrics']['output_tokens']} / {log['metrics']['embed_tokens']}")
                        st.divider()
def page_admin_cost():
    render_welcome_banner()
    st.title("Cost & Token Analytics (Monitor A)")
    
    total_registered_users = run_async(raw_db["users"].count_documents({}))
    logs = run_async(raw_db["usage_logs"].find().sort("timestamp", 1).to_list(length=10000))
    
    if not logs:
        st.info(f"Total Registered Users: {total_registered_users}. No operational chat data recorded yet.")
        return
        
    df = pd.json_normalize(logs)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    start_period = df['timestamp'].min().strftime('%Y-%m-%d %H:%M:%S UTC')
    end_period = df['timestamp'].max().strftime('%Y-%m-%d %H:%M:%S UTC')
    
    st.warning(f"**Analytics Reporting Window:** From {start_period} to {end_period}")
    
    total_spend = df['cost_usd.total'].sum()
    total_tokens = df['metrics.input_tokens'].sum() + df['metrics.output_tokens'].sum() + df['metrics.embed_tokens'].sum()
    total_conversations = df['session_id'].nunique()
    active_users = df['user_id'].nunique()
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Platform Spend (Window)", f"${total_spend:.5f}")
    m2.metric("Total Tokens Processed", f"{total_tokens:,}")
    m3.metric("Total Conversations", f"{total_conversations}")
    m4.metric("Active / Registered Users", f"{active_users} / {total_registered_users}")
    
    st.divider()
    
    st.subheader("High-Volume User Aggregations")
    user_summary = df.groupby('user_id').agg(
        Total_Spend=('cost_usd.total', 'sum'),
        Total_Messages=('session_id', 'count'),
        LLM_Input_Tokens=('metrics.input_tokens', 'sum'),
        LLM_Output_Tokens=('metrics.output_tokens', 'sum')
    ).reset_index().sort_values(by="Total_Spend", ascending=False)
    
    user_summary.columns = ["User ID", "Total Spend (USD)", "Total Messages Sent", "Input Tokens Count", "Output Tokens Count"]
    st.dataframe(user_summary, use_container_width=True, hide_index=True)

def page_admin_estimation():
    render_welcome_banner()
    st.title("Dynamic Cost & Scaling Estimation Model")
    st.markdown("Calculate system resource scaling matrices based on current API execution cost thresholds, incorporating Groq's 50% Prefix Cache discount on static prompts.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Simulation Parameters")
        est_mau = st.number_input("Expected Monthly Active Users (MAU)", min_value=1, value=1000, step=100)
        est_conv = st.number_input("Average Conversations per User / Month", min_value=1.0, value=2.0, step=0.5)
        est_msg = st.number_input("Average Messages per Conversation", min_value=1.0, value=6.0, step=1.0)
        
        st.markdown("##### Token Architecture")
        static_prefix = st.number_input("Static System Prompt + Tool Schemas (Cached)", min_value=100, value=1021, step=50)
        dynamic_context = st.number_input("Dynamic Context per Turn (History + RAG)", min_value=100, value=3000, step=500)
        est_out_tokens = st.number_input("Estimated Output Tokens per Turn", min_value=50, value=350, step=50)
        cache_hit_rate = st.slider("Target Semantic Cache Hit Rate (%)", min_value=0, max_value=100, value=30)
        
    with col2:
        st.subheader("Financial & Scaling Forecast Matrix")
        
        total_monthly_messages = int(est_mau * est_conv * est_msg)
        uncached_messages = int(total_monthly_messages * (1 - (cache_hit_rate / 100)))
        
        # Groq charges 50% less for cached static prefix tokens ($0.075 per 1M)
        total_static_tokens = uncached_messages * static_prefix
        total_dynamic_tokens = uncached_messages * dynamic_context
        total_out_tokens = uncached_messages * est_out_tokens
        
        # Embedding vector calculation based on dynamic context size
        total_embed_tokens = total_monthly_messages * (dynamic_context // 4) * 2
        
        cost_groq_cached = (total_static_tokens / 1_000_000) * 0.075
        cost_groq_dynamic = (total_dynamic_tokens / 1_000_000) * 0.15
        cost_groq_out = (total_out_tokens / 1_000_000) * 0.60
        cost_gemini_embed = (total_embed_tokens / 1_000_000) * 0.10
        
        total_estimated_monthly_spend = cost_groq_cached + cost_groq_dynamic + cost_groq_out + cost_gemini_embed
        
        st.metric("Total Projected Monthly Messages", f"{total_monthly_messages:,}")
        st.metric("Estimated Monthly API Bill", f"${total_estimated_monthly_spend:.2f}")
        
        breakdown_data = [
            {"System Component": "Groq Cached Prefix (System+Tools)", "Tokens": f"{total_static_tokens:,}", "Rate per 1M": "$0.075", "Cost": f"${cost_groq_cached:.4f}"},
            {"System Component": "Groq Dynamic Input (RAG+History)", "Tokens": f"{total_dynamic_tokens:,}", "Rate per 1M": "$0.150", "Cost": f"${cost_groq_dynamic:.4f}"},
            {"System Component": "Groq LLM Output (Response)", "Tokens": f"{total_out_tokens:,}", "Rate per 1M": "$0.600", "Cost": f"${cost_groq_out:.4f}"},
            {"System Component": "Gemini Vector Embeddings", "Tokens": f"{total_embed_tokens:,}", "Rate per 1M": "$0.100", "Cost": f"${cost_gemini_embed:.4f}"}
        ]
        st.table(pd.DataFrame(breakdown_data))

def page_admin_trace():
    render_welcome_banner()
    st.title("Behavior & Trace Monitor (Monitor B)")
    
    users = run_async(raw_db["users"].find().to_list(length=100))
    if not users:
        st.warning("No telemetry profiles isolated.")
        return
        
    tabs = st.tabs([u["username"] for u in users])
    
    for idx, user in enumerate(users):
        with tabs[idx]:
            logs = run_async(raw_db["usage_logs"].find({"user_id": user["user_id"]}).sort("timestamp", -1).to_list(length=50))
            if not logs:
                st.info("No recorded context transitions for this identifier.")
                continue
                
            for log in logs:
                is_hit = log.get("is_cache_hit", False)
                title_label = f"⚡ SEMANTIC CACHE HIT | {log['timestamp']}" if is_hit else f"Inference Roundtrip | {log['timestamp']}"
                
                with st.expander(f"{title_label} | Allocation: ${log['cost_usd']['total']:.5f}"):
                    st.markdown(f"**User Prompt:** <div class='rtl-text'>{log['behavior']['prompt_snippet']}</div>", unsafe_allow_html=True)
                    st.markdown(f"**Agent Generation:** <div class='rtl-text'>{log['behavior']['response_snippet']}</div>", unsafe_allow_html=True)
                    st.json(log['behavior']['tools_called'])
                    st.caption(f"Latency: {log['metrics']['latency_ms']:.2f}ms | Hardware Allocation (In / Out / Embed): {log['metrics']['input_tokens']} / {log['metrics']['output_tokens']} / {log['metrics']['embed_tokens']}")

if st.session_state.user_id is None:
    page_auth()
else:
    if st.session_state.role == "admin":
        with st.sidebar:
            render_sidebar_logo()
            st.markdown("### Admin System Controls")
            if st.sidebar.button("System Logout", use_container_width=True):
                st.session_state.clear()
                st.rerun()
                
        pg = st.navigation([
            st.Page(page_admin_crm, title="CRM Lead Tickets"),
            st.Page(page_admin_cost, title="Platform Cost Analyzer"),
            st.Page(page_admin_estimation, title="Dynamic Cost Estimator"),
            st.Page(page_admin_trace, title="Granular Behavior Trace")
        ])
        pg.run()
    else:
        page_chat()
