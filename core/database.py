from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import pytz
from core.config import MONGO_URI, CRM_DB_NAME, LEADS_COLLECTION

class CRMDatabase:
    def __init__(self):
        # Establish connection using the URI from .env
        self.client = AsyncIOMotorClient(MONGO_URI)
        self.db = self.client[CRM_DB_NAME]
        self.collection = self.db[LEADS_COLLECTION]

    async def capture_lead(
        self, 
        name: str, 
        phone_data: dict, 
        email_data: dict, 
        intent: str, 
        recommended_product: str, 
        summary: str, 
        objections: str,
        dynamic_info: dict  # <-- This makes it dynamic!
    ) -> str:
        
        cairo_tz = pytz.timezone("Africa/Cairo")
        
        # Base strictly formatted schema for the sales team
        ticket = {
            "ticket_id": f"LEAD-{datetime.now(cairo_tz).strftime('%Y%m%d%H%M%S')}",
            "الاسم": name,
            "رقم التواصل": phone_data.get("formatted_number", ""),
            "البريد الإلكتروني": email_data.get("email", "غير متوفر"),
            "البلد": phone_data.get("country", "غير معروف"),
            "الكورسات محل الاهتمام": recommended_product,
            "الاعتراضات": objections,
            "ملخّص المحادثة": summary,
            "الإجراء التالي": "يتواصل أحد مندوبي المبيعات عبر واتساب أو البريد خلال ٢٤ ساعة لتأكيد التسجيل",
            "التاريخ": datetime.now(cairo_tz).strftime("%Y-%m-%d %H:%M:%S"),
            "حالة_التذكرة": "ساخن"
        }
        
        # Inject any extra dynamic info the agent found into a clean sub-document
        if dynamic_info and isinstance(dynamic_info, dict):
            ticket["معلومات_إضافية"] = dynamic_info
            
        result = await self.collection.insert_one(ticket)
        return str(result.inserted_id)
