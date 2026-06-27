import hashlib
import uuid
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

class AuthManager:
    def __init__(self, mongo_uri: str, db_name: str):
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client[db_name]
        self.users = self.db["users"]

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    async def register(self, username: str, password: str) -> str:
        existing = await self.users.find_one({"username": username})
        if existing:
            raise ValueError("Username exists")
        
        user_id = str(uuid.uuid4())
        await self.users.insert_one({
            "user_id": user_id,
            "username": username,
            "password_hash": self._hash_password(password),
            "created_at": datetime.now(timezone.utc)
        })
        return user_id

    async def login(self, username: str, password: str) -> tuple[str, str]:
        user = await self.users.find_one({
            "username": username,
            "password_hash": self._hash_password(password)
        })
        if not user:
            raise ValueError("Invalid credentials")
            
        session_id = str(uuid.uuid4())
        return user["user_id"], session_id
