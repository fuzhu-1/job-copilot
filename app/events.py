import queue
from typing import Any


class EventBus:
    """线程安全事件总线：后台任务发布事件，SSE 生成器订阅。"""

    def __init__(self):
        self._queues: dict[str, list[queue.Queue]] = {}

    def publish(self, task_id: str, event: dict[str, Any]) -> None:
        for q in self._queues.get(task_id, []):
            q.put(event)

    def subscribe(self, task_id: str) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        self._queues.setdefault(task_id, []).append(q)
        return q

    def unsubscribe(self, task_id: str, q: queue.Queue) -> None:
        if task_id in self._queues and q in self._queues[task_id]:
            self._queues[task_id].remove(q)
            if not self._queues[task_id]:
                del self._queues[task_id]


event_bus = EventBus()
