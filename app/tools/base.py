from typing import Any, Callable

ToolFn = Callable[..., Any]


class ToolRouter:
    """工具注册与路由。Phase 2 起由 Supervisor 按需调用。"""

    def __init__(self):
        self._tools: dict[str, ToolFn] = {}

    def register(self, name: str, fn: ToolFn) -> None:
        self._tools[name] = fn

    def execute(self, name: str, **kwargs: Any) -> Any:
        if name not in self._tools:
            raise KeyError(f"tool not found: {name}")
        return self._tools[name](**kwargs)
