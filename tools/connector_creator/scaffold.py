# tools/connector_creator/scaffold.py
# Convenience helper: creates a new connector folder from a template.
# Run it, give a tool name and permission level, and it builds the folder
# with a connector.json and a starter tool file ready to fill in.
#
# Usage (from project root):
#   python -m tools.connector_creator.scaffold weather read_only
#
# This does NOT register the tool — the registry auto-discovers it on next
# startup because it now has a connector.json. You still write the real logic.

import os
import sys
import json

VALID_LEVELS = ("read_only", "write_gated", "always_gated")

# tools/ is one level up from this file's folder.
_TOOLS_DIR = os.path.dirname(os.path.dirname(__file__))


def scaffold(name: str, permission_level: str) -> None:
    if permission_level not in VALID_LEVELS:
        print(f"Bad permission level '{permission_level}'. Use one of: {VALID_LEVELS}")
        return

    folder = os.path.join(_TOOLS_DIR, name)
    if os.path.exists(folder):
        print(f"Folder '{name}' already exists. Aborting — nothing changed.")
        return

    os.makedirs(folder)

    # connector.json — the tool's ID card.
    manifest = {
        "name": name,
        "version": "1.0.0",
        "description": f"TODO: describe what {name} does.",
        "permission_level": permission_level,
        "enabled": True,
    }
    with open(os.path.join(folder, "connector.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4)

    # __init__.py
    with open(os.path.join(folder, "__init__.py"), "w", encoding="utf-8") as f:
        f.write(f"# tools/{name}/ — connector package.\n")

    # Starter tool file inheriting BaseConnector.
    tool_code = f'''# tools/{name}/{name}_tool.py
# TODO: fill in validate() and execute().

from tools.base_connector import BaseConnector


class {_class_name(name)}(BaseConnector):
    name = "{name}"
    version = "1.0.0"
    description = "TODO: describe what {name} does."
    permission_level = "{permission_level}"

    def validate(self, payload: dict) -> bool:
        # TODO: check the input is well-formed.
        return True

    def execute(self, payload: dict) -> dict:
        # TODO: do the real work.
        return {{"status": "not_implemented", "output": None}}
'''
    with open(os.path.join(folder, f"{name}_tool.py"), "w", encoding="utf-8") as f:
        f.write(tool_code)

    print(f"Created tools/{name}/ with connector.json, __init__.py, {name}_tool.py")
    print("Next: fill in validate() and execute(). Registry will find it on next startup.")


def _class_name(name: str) -> str:
    """web_search -> WebSearchConnector"""
    return "".join(part.capitalize() for part in name.split("_")) + "Connector"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m tools.connector_creator.scaffold <name> <permission_level>")
        print(f"permission_level one of: {VALID_LEVELS}")
        sys.exit(1)
    scaffold(sys.argv[1], sys.argv[2])