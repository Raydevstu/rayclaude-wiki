from tier1.store import Store


def test_task_lifecycle_and_interrupted_recovery_are_persisted():
    store = Store(":memory:")
    store.task_put("t1", "running", {"prompt": "hello", "progress": 10})
    store.task_event_add("t1", "started", {"progress": 10})
    assert store.task_get("t1")["status"] == "running"
    assert store.task_events("t1")[0]["kind"] == "started"
    assert store.reconcile_interrupted_tasks() == 1
    assert store.task_get("t1")["status"] == "interrupted"
    assert store.task_events("t1")[-1]["kind"] == "interrupted"


def test_tasks_list_and_events_can_be_read_after_restart():
    store = Store(":memory:")
    store.task_put("t2", "done", {"prompt": "answer", "progress": 100})
    store.task_event_add("t2", "completed", {"status": "done"})

    assert store.tasks_list() == [{"id": "t2", "status": "done"}]
    assert store.task_events("t2")[0]["kind"] == "completed"
