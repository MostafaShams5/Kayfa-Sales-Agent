import hashlib
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient

class MongoSemanticCache:
    def __init__(self, mongo_uri: str, db_name: str, collection_name: str, embedding_service):
        self.client = AsyncIOMotorClient(mongo_uri)
        self.collection = self.client[db_name][collection_name]
        self.embedding_service = embedding_service

    async def get_cached_response(self, query: str, context_hash: str, threshold: float = 0.88) -> Optional[str]:
        query_vector, _ = await self.embedding_service.generate_embedding(query)
        
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": 10,
                    "limit": 1
                }
            },
            {
                "$match": {
                    "context_hash": context_hash
                }
            },
            {
                "$project": {
                    "response": 1,
                    "score": {"$meta": "vectorSearchScore"}
                }
            }
        ]
        
        results = await self.collection.aggregate(pipeline).to_list(length=1)
        
        if results and results[0].get("score", 0) >= threshold:
            return results[0]["response"]
            
        return None

    async def set_cached_response(self, query: str, response: str, context_hash: str) -> None:
        query_vector, _ = await self.embedding_service.generate_embedding(query)
        
        document = {
            "query": query,
            "response": response,
            "embedding": query_vector,
            "context_hash": context_hash
        }
        
        await self.collection.insert_one(document)

    @staticmethod
    def generate_context_hash(history: list) -> str:
        if not history:
            return hashlib.sha256(b"empty").hexdigest()
        history_str = "".join([str(msg) for msg in history[-2:]])
        return hashlib.sha256(history_str.encode()).hexdigest()


class UserHistoryRAG:
    def __init__(self, mongo_uri: str, db_name: str, collection_name: str, embedding_service):
        self.client = AsyncIOMotorClient(mongo_uri)
        self.collection = self.client[db_name][collection_name]
        self.embedding_service = embedding_service

    async def retrieve_user_history(self, query: str, user_id: str, threshold: float = 0.75) -> str:
        query_vector, _ = await self.embedding_service.generate_embedding(query)
        
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": 10,
                    "limit": 3
                }
            },
            {
                "$match": { "user_id": user_id }
            },
            {
                "$project": {
                    "query": 1,
                    "response": 1,
                    "score": {"$meta": "vectorSearchScore"}
                }
            }
        ]
        
        results = await self.collection.aggregate(pipeline).to_list(length=3)
        relevant_history = [r for r in results if r.get("score", 0) >= threshold]
        
        if not relevant_history:
            return ""
            
        history_text = "--- PAST USER CONTEXT RECALLED FROM MEMORY ---\n"
        for r in relevant_history:
            history_text += f"Previous Query: {r['query']}\nPrevious Answer: {r['response']}\n\n"
        return history_text

    async def save_interaction(self, user_id: str, query: str, response: str) -> None:
        query_vector, _ = await self.embedding_service.generate_embedding(query)
        
        document = {
            "user_id": user_id,
            "query": query,
            "response": response,
            "embedding": query_vector
        }
        
        await self.collection.insert_one(document)
