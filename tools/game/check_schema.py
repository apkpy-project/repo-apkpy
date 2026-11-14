"""Checks that the Java readers know every component, field and action of the schema.

    python src/tools/check_schema.py

The schema (src/python/apkpygame/schema/components.json) is what the
declaration reader accepts; ComponentTypes.java is what the engine reads.
A field in one and not the other would be accepted at build and silently
ignored on the phone: the failure this project refuses to have.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # ApkPy's repository
TOOLS = os.path.join(ROOT, "tools", "game")
SRC = ROOT
SCHEMA = os.path.join(ROOT, "apkpy_lib", "game", "schema", "components.json")
JAVA = os.path.join(ROOT, "game_engine", "java", "core", "apkpygame", "core", "ComponentTypes.java")
ACTIONS = os.path.join(ROOT, "game_engine", "java", "core", "apkpygame", "core", "Actions.java")


def reader_body(java, name):
    m = re.search(r'register\("%s", new Reader\(\) \{(.*?)\n        \}\);' % name, java, re.S)
    return m.group(1) if m else None


def main():
    with open(SCHEMA, encoding="utf-8") as fh:
        schema = json.load(fh)
    with open(JAVA, encoding="utf-8") as fh:
        java = fh.read()
    problems = []
    for c in schema["components"]:
        body = reader_body(java, c["name"])
        if body is None:
            problems.append("component %s: no register(\"%s\", ...) in ComponentTypes.java" % (c["name"], c["name"]))
            continue
        for field, spec in c["fields"].items():
            if spec.get("python_only"):
                continue
            key = spec.get("json", field)
            if '"%s"' % key not in body:
                problems.append("%s.%s: the Java reader never reads \"%s\"" % (c["name"], field, key))
    with open(ACTIONS, encoding="utf-8") as fh:
        actions = re.search(r"static Action read\(Map<String, Object> a, Game game\) \{(.*?)\n    \}", fh.read(),
                            re.S).group(1)
    for a in schema["actions"]:
        if 'kind.equals("%s")' % a["do"] not in actions:
            problems.append("action %s: Java does not handle do=\"%s\"" % (a["name"], a["do"]))
        for field, spec in a["fields"].items():
            if '"%s"' % spec.get("json", field) not in actions:
                problems.append("action %s.%s: the Java reader never reads it" % (a["name"], field))
    if problems:
        print("schema and engine disagree:\n  " + "\n  ".join(problems))
        sys.exit(1)
    print("schema OK: %d components, %d actions, every field read by the engine"
          % (len(schema["components"]), len(schema["actions"])))


if __name__ == "__main__":
    main()
