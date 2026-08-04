import html as html_module
import re
import urllib.parse

import httpx

from app.config import settings


class SearchTool:
    """网页搜索工具。配置了 Tavily Key 时走 API；否则回退 DuckDuckGo HTML 搜索（免 Key）。"""

    def __init__(self, api_key: str | None = None, provider: str | None = None):
        self.api_key = api_key if api_key is not None else settings.search_api_key
        self.provider = provider or settings.search_provider

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if self.provider == "tavily" and self.api_key:
            return self._search_tavily(query, top_k)
        return self._search_duckduckgo(query, top_k)

    def _search_tavily(self, query: str, top_k: int) -> list[dict]:
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

    def _search_duckduckgo(self, query: str, top_k: int) -> list[dict]:
        """抓取 DuckDuckGo HTML 结果（免 Key）。解析失败时返回空列表。"""
        try:
            response = httpx.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                timeout=15.0,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            response.raise_for_status()
        except Exception:
            return []
        html = response.text
        matches = re.findall(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            html,
            re.S,
        )
        snippets = re.findall(
            r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', html, re.S
        )
        results = []
        for i, (href, title) in enumerate(matches[:top_k]):
            url = href
            uddg = re.search(r"[?&]uddg=([^&]+)", href)
            if uddg:
                url = urllib.parse.unquote(uddg.group(1))
            content = ""
            if i < len(snippets):
                content = html_module.unescape(
                    re.sub(r"<[^>]+>", "", snippets[i])
                ).strip()
            results.append(
                {
                    "title": html_module.unescape(re.sub(r"<[^>]+>", "", title)).strip(),
                    "url": url,
                    "content": content[:300],
                }
            )
        return results
