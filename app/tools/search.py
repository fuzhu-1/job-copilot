import httpx

from app.config import settings


class SearchTool:
    """网页搜索工具。provider=tavily 时调用 API；未配置 Key 时返回空列表（调用方降级）。"""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key if api_key is not None else settings.search_api_key

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not self.api_key:
            return []
        response = httpx.post(
            "https://api.tavily.com/search",
            json={"api_key": self.api_key, "query": query, "max_results": top_k},
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
            }
            for item in data.get("results", [])[:top_k]
        ]
