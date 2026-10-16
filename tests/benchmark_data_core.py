"""Small repeatable Data Core benchmark used by the 1.3.0 release checklist."""

import os
import tempfile
import threading
from time import perf_counter

from apkpy_lib import SQLiteAPI


def wait_for(start):
    event = threading.Event()
    result = {}

    def success(value):
        result["value"] = value
        event.set()

    def failure(message):
        result["error"] = message
        event.set()

    future = start(success, failure)
    future.result(timeout=60)
    if not event.wait(60):
        raise RuntimeError("callback timeout")
    if "error" in result:
        raise RuntimeError(result["error"])
    return result.get("value")


print("rows,insert_many_ms,indexed_page_ms,count_ms,database_bytes")
for size in (1, 1000, 10000):
    database = SQLiteAPI()
    folder = tempfile.mkdtemp(prefix=f"apkpy-data-{size}-")
    database._path = os.path.join(folder, "benchmark.db")
    records = database.model("records", fields={
        "id": database.integer(primary_key=True, auto_increment=True),
        "title": database.text(required=True, max_length=120),
        "favorite": database.boolean(default=False),
        "score": database.integer(default=0, min_value=0, max_value=100),
        "metadata": database.json(optional=True),
        "updated_at": database.datetime(default=database.now()),
    }, indexes=[
        database.index("idx_records_favorite_updated", ["favorite", "updated_at"]),
    ])
    database.schema("benchmark", 1, [records])
    values = [
        {
            "title": f"Record {index}",
            "favorite": index % 3 == 0,
            "score": index % 101,
            "metadata": {"position": index},
        }
        for index in range(size)
    ]

    started = perf_counter()
    wait_for(lambda ok, fail: records.insert_many(
        values, on_result=ok, on_error=fail,
    ))
    insert_ms = (perf_counter() - started) * 1000

    started = perf_counter()
    rows = wait_for(lambda ok, fail: records.find(
        filters=[database.eq("favorite", True)],
        order_by=[database.desc("updated_at")],
        limit=30,
        offset=0,
        on_result=ok,
        on_error=fail,
    ))
    page_ms = (perf_counter() - started) * 1000
    assert len(rows) == min(30, (size + 2) // 3)

    started = perf_counter()
    wait_for(lambda ok, fail: records.count(
        filters=[database.gte("score", 50)],
        on_result=ok,
        on_error=fail,
    ))
    count_ms = (perf_counter() - started) * 1000

    print(
        f"{size},{insert_ms:.2f},{page_ms:.2f},{count_ms:.2f},"
        f"{os.path.getsize(database._path)}"
    )

