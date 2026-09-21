import os

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()


class WebSearch:

    def __init__(self):

        api_key = os.getenv("TAVILY_API_KEY")

        if not api_key:
            raise ValueError("TAVILY_API_KEY not found in .env")

        self.client = TavilyClient(api_key=api_key)

    def search(self, query: str, max_results: int = 5):

        if not query or not query.strip():
            raise ValueError("Search query cannot be empty.")

        response = self.client.search(
            query=query.strip(),
            search_depth="basic",
            max_results=max_results,
        )

        return response.get("results", [])