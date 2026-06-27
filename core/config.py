import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
# The model string for Pydantic AI Groq integration
MODEL_NAME = "groq:openai/gpt-oss-120b"

CRM_DB_NAME = "kayfa_crm"
LEADS_COLLECTION = "leads"
