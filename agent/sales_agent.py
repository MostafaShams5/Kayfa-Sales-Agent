import json
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext
from core.knowledge_base import KnowledgeBase
from core.database import CRMDatabase
from core.config import MODEL_NAME
from core.validators import validate_and_format_phone, validate_email
from core.memory import TokenOptimizer

@dataclass
class AgentDeps:
    kb: KnowledgeBase
    db: CRMDatabase

kayfa_sales_agent = Agent(
    MODEL_NAME,
    deps_type=AgentDeps,
    system_prompt=(
        "You are the Kayfa AI Sales Agent. You are a persuasive, helpful, and strictly honest educational consultant.\n\n"
        "1. GROUNDING: If a tool returns `[]`, `error`, or 'not found', YOU MUST TELL THE USER WE DO NOT HAVE IT.\n"
        "2. PRODUCT RULES: On-Demand Tracks have fixed prices and end in '_track'. Live Diplomas are 5-month bootcamps, price is 'Contact Sales', and end in '_diploma'.\n"
        "3. LEAD CAPTURE & VALIDATION (STRICT RULES):\n"
        "   - When a user wants to enroll, ask for their Name and AT LEAST ONE contact method (Phone number OR Email).\n"
        "   - DO NOT GUESS if a phone number or email is valid. You cannot run Regex. You MUST pass the user's input to the `validate_contact_info` tool immediately.\n"
        "   - If validation fails, tell the user the exact error and ask them to fix it.\n"
        "   - EXECUTION BARRIER: You are STRICTLY FORBIDDEN from confirming registration until you have successfully executed `capture_crm_lead`.\n"
        "4. Write CRM summaries STRICTLY in Arabic, keeping technical terms in English.\n"
        "5. FORMATTING: Respond to the user in plain text only and understandable."
    )
)

@kayfa_sales_agent.tool
async def search_catalog(ctx: RunContext[AgentDeps], query: str, max_price: float, free_only: bool) -> str:
    """Search the Kayfa knowledge base for courses or tracks based on a query or skill."""
    safe_max_price = max_price if max_price > 0 else None
    results = ctx.deps.kb.search_catalog(query, safe_max_price, free_only)
    optimized_results = TokenOptimizer.compress_tool_output(results, ["type", "id", "name", "price"])
    return json.dumps(optimized_results, ensure_ascii=False)

@kayfa_sales_agent.tool
async def get_program_details(ctx: RunContext[AgentDeps], program_id: str) -> str:
    """Retrieve full curriculum, duration, and level details for a specific program ID."""
    details = ctx.deps.kb.get_program_details(program_id)
    optimized_details = TokenOptimizer.compress_dict(details, ["id", "name", "duration", "level", "price", "is_free"])
    return json.dumps(optimized_details, ensure_ascii=False)

@kayfa_sales_agent.tool
async def get_diploma_pitch(ctx: RunContext[AgentDeps], diploma_id: str) -> str:
    """Get the persuasive sales pitch and career growth info for a live diploma."""
    pitch = ctx.deps.kb.get_diploma_pitch(diploma_id)
    optimized_pitch = TokenOptimizer.compress_dict(pitch, ["name", "pitch", "closing_value"])
    return json.dumps(optimized_pitch, ensure_ascii=False)

@kayfa_sales_agent.tool
async def get_company_policy(ctx: RunContext[AgentDeps], topic: str) -> str:
    """Retrieve official Kayfa policies regarding refunds, privacy, or general FAQs."""
    return ctx.deps.kb.get_policy(topic)

@kayfa_sales_agent.tool
async def validate_contact_info(ctx: RunContext[AgentDeps], phone: str, email: str) -> str:
    """Always use this tool to check if a phone number or email is formatted correctly before trying to save a lead."""
    response = []
    
    if phone and phone.strip() not in ["", "None", "null", "لا يوجد"]:
        phone_data = validate_and_format_phone(phone)
        if not phone_data["is_valid"]:
            response.append(f"PHONE ERROR: {phone_data['error_message']}")
        else:
            response.append(f"PHONE VALID: Formatted as {phone_data['formatted_number']}")
            
    if email and email.strip() not in ["", "None", "null", "لا يوجد"]:
        email_data = validate_email(email)
        if not email_data["is_valid"]:
            response.append(f"EMAIL ERROR: {email_data['error_message']}")
        else:
            response.append(f"EMAIL VALID: {email_data['email']}")
            
    if not response:
        return "ERROR: You must provide at least a phone number or an email to validate."
        
    return " | ".join(response)

@kayfa_sales_agent.tool
async def capture_crm_lead(
    ctx: RunContext[AgentDeps], 
    name: str, 
    phone: str, 
    intent: str, 
    recommended_product: str, 
    summary: str, 
    email: str, 
    objections: str,
    dynamic_extra_info_json: str
) -> str:
    """Save a qualified lead securely into the MongoDB CRM system."""
    if not name or (not phone and not email):
        return "ERROR: Missing name, or missing both phone and email. You need the name and at least one contact method."
        
    phone_data = {"is_valid": False, "formatted_number": "غير متوفر", "country": "غير معروف"}
    if phone and phone.strip() not in ["", "None", "null", "لا يوجد"]:
        phone_data = validate_and_format_phone(phone)
        if not phone_data["is_valid"]:
            return f"ERROR: {phone_data['error_message']}"
        
    email_data = {"is_valid": False, "email": "غير متوفر"}
    if email and email.strip() not in ["", "None", "null", "لا يوجد"]:
        email_data = validate_email(email)
        if not email_data["is_valid"]:
            return f"ERROR: {email_data['error_message']}"

    safe_objections = objections if objections and objections.strip() else "لا يوجد"

    dynamic_info = {}
    try:
        if dynamic_extra_info_json and dynamic_extra_info_json.strip() not in ["", "{}"]:
            dynamic_info = json.loads(dynamic_extra_info_json)
    except json.JSONDecodeError:
        pass

    ticket_id = await ctx.deps.db.capture_lead(
        name=name,
        phone_data=phone_data,
        email_data=email_data,
        intent=intent,
        recommended_product=recommended_product,
        summary=summary,
        objections=safe_objections,
        dynamic_info=dynamic_info
    )
    
    return f"SUCCESS: Lead captured securely in CRM. Ticket ID: {ticket_id}."
