from app.events import EventBus


def test_publish_subscribe_and_unsubscribe():
    bus = EventBus()
    q = bus.subscribe("t1")
    bus.publish("t1", {"type": "started"})
    assert q.get(timeout=1)["type"] == "started"
    bus.unsubscribe("t1", q)
    assert "t1" not in bus._queues


def test_multiple_subscribers():
    bus = EventBus()
    q1 = bus.subscribe("t1")
    q2 = bus.subscribe("t1")
    bus.publish("t1", {"type": "x"})
    assert q1.get(timeout=1)["type"] == "x"
    assert q2.get(timeout=1)["type"] == "x"
