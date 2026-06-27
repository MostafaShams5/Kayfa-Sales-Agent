from typing import Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorClient

class CostAnalytics:
    def __init__(self, mongo_uri: str, db_name: str):
        self.client = AsyncIOMotorClient(mongo_uri)
        self.collection = self.client[db_name]["usage_logs"]

    async def get_cost_per_user(self) -> List[Dict[str, Any]]:
        pipeline = [
            {"$group": {"_id": "$user_id", "total_cost": {"$sum": "$cost_usd.total"}}},
            {"$sort": {"total_cost": -1}}
        ]
        return await self.collection.aggregate(pipeline).to_list(length=None)

    async def get_cost_per_session(self, user_id: str) -> List[Dict[str, Any]]:
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": "$session_id", "total_cost": {"$sum": "$cost_usd.total"}}},
            {"$sort": {"total_cost": -1}}
        ]
        return await self.collection.aggregate(pipeline).to_list(length=None)

    async def get_monthly_costs(self) -> List[Dict[str, Any]]:
        pipeline = [
            {
                "$group": {
                    "_id": {
                        "year": {"$year": "$timestamp"},
                        "month": {"$month": "$timestamp"}
                    },
                    "monthly_cost": {"$sum": "$cost_usd.total"}
                }
            },
            {"$sort": {"_id.year": 1, "_id.month": 1}}
        ]
        return await self.collection.aggregate(pipeline).to_list(length=None)
