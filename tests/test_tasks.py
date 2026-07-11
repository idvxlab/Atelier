from __future__ import annotations

from harness.types.tasks import TaskStatus, build_task_records


def test_build_task_records_unifies_plan_queue_and_spawn():
    records = build_task_records(
        "session-1",
        todos=[
            {
                "item_id": "item_1",
                "content": "Design the information architecture",
                "status": "in_progress",
                "assigned_session_id": "sub_abc",
            }
        ],
        pending_commands=[
            {
                "index": 2,
                "text": "Then generate the copy",
                "submitted_at": 1710000000.0,
            }
        ],
        pending_spawns=[
            {
                "index": 3,
                "sub_id": "sub_def",
                "display_name": "Content agent",
                "task": "Draft admission page content",
                "submitted_at": 1710000001.0,
            }
        ],
    )

    assert [record.source for record in records] == [
        "plan_item",
        "queued_command",
        "subagent",
    ]
    assert records[0].status == TaskStatus.RUNNING
    assert records[0].related_session_id == "sub_abc"
    assert records[1].status == TaskStatus.QUEUED
    assert records[1].index == 2
    assert records[2].status == TaskStatus.RUNNING
    assert records[2].related_session_id == "sub_def"


def test_task_record_serialization_uses_status_values():
    record = build_task_records(
        "session-1",
        todos=[{"item_id": "done", "content": "Ship", "status": "completed"}],
    )[0]

    data = record.to_dict()
    assert data["task_id"] == "plan:session-1:done"
    assert data["status"] == "completed"
    assert data["source"] == "plan_item"
