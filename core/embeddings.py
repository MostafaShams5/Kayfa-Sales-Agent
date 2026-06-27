import os
from google import genai
from google.genai import types

class GeminiEmbeddingService:
    def __init__(self):
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        self.model_name = "gemini-embedding-2"
        self.dimensions = 768

    async def generate_embedding(self, text: str) -> tuple[list[float], int]:
        if not text or not text.strip():
            return [0.0] * self.dimensions, 0
            
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=text.strip(),
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=self.dimensions
            )
        )
        token_count = len(text) // 4
        return response.embeddings[0].values, token_count
