"""Smoke test executed with the clean release virtual environment."""

from importlib.metadata import version
import os
import tempfile
import threading

import apkpy_lib
from apkpy_lib import SQLiteAPI
from apkpy_lib.core.compiler import translate_python_to_android


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
    future.result(timeout=10)
    if not event.wait(10):
        raise AssertionError("Data callback timed out")
    if "error" in result:
        raise AssertionError(result["error"])
    return result.get("value")


assert version("apkpy") == "1.3.0"
assert "site-packages" in os.path.abspath(apkpy_lib.__file__).lower(), apkpy_lib.__file__

database = SQLiteAPI()
directory = tempfile.mkdtemp(prefix="apkpy-wheel-data-")
database._path = os.path.join(directory, "clean-install.db")
notes = database.model("notes", fields={
    "id": database.integer(primary_key=True, auto_increment=True),
    "title": database.text(required=True),
    "metadata": database.json(optional=True),
})
database.schema("wheel_smoke", 1, [notes])
inserted = wait_for(lambda ok, fail: notes.insert(
    {"title": "Clean wheel", "metadata": {"version": "1.3.0"}},
    on_result=ok,
    on_error=fail,
))
row = wait_for(lambda ok, fail: notes.get(inserted, on_result=ok, on_error=fail))
assert row["title"] == "Clean wheel"
assert row["metadata"]["version"] == "1.3.0"

generated = translate_python_to_android(
    "from apkpy_lib import *\n"
    "items=db.model('items',fields={'id':db.integer(primary_key=True)})\n"
    "schema=db.schema('wheel_app',1,[items])\n"
    "home=Screen(id='home')\nlabel('OK',screen=home)\nrun(start_screen=home)\n"
)
assert "error.txt" not in generated, generated.get("error.txt")
assert "java/ApkpyDatabase.java" in generated
assert "java/ItemsRepository.java" in generated

print("clean wheel OK", version("apkpy"), apkpy_lib.__file__)

