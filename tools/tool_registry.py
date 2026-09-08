# tools/tool_registry.py
# Auto-discovers connectors by scanning the tools/ folder for connector.json files.
# The orchestrator asks the registry: does a tool exist, and does it need approval?
# Adding a tool = drop a folder with connector.json. No code editing here.

import os
import json
import importlib

# Permission levels must match base_connector.py.
VALID_PERMISSION_LEVELS = frozenset({"read_only", "write_gated", "always_gated"})

# Folder this file lives in = the tools/ folder.
_TOOLS_DIR = os.path.dirname(__file__)

# Loaded once at import. {tool_name: manifest_dict}
_REGISTRY: dict = {}


def _discover() -> dict:
    """Scan tools/ for connector.json files. Build the registry."""
    registry = {}
    for entry in os.listdir(_TOOLS_DIR):
        folder = os.path.join(_TOOLS_DIR, entry)
        if not os.path.isdir(folder):
            continue
        manifest_path = os.path.join(folder, "connector.json")
        if not os.path.exists(manifest_path):
            continue
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception as e:
            print(f"[tool_registry] Skipping {entry}: bad connector.json ({e})")
            continue

        # Defensive checks — a malformed manifest must not crash startup.
        name = manifest.get("name")
        level = manifest.get("permission_level")
        if not name:
            print(f"[tool_registry] Skipping {entry}: no name in connector.json")
            continue
        if level not in VALID_PERMISSION_LEVELS:
            print(f"[tool_registry] Skipping {name}: bad permission_level '{level}'")
            continue

        registry[name] = manifest
    return registry


def reload_registry() -> None:
    """Re-scan the tools folder. Call after adding a tool at runtime."""
    global _REGISTRY
    _REGISTRY = _discover()


def list_tools(include_disabled: bool = False) -> list:
    """Return the names of all registered tools."""
    if include_disabled:
        return list(_REGISTRY.keys())
    return [n for n, m in _REGISTRY.items() if m.get("enabled", True)]


def get_tool(name: str) -> dict | None:
    """Return a tool's manifest, or None if not found or disabled."""
    manifest = _REGISTRY.get(name)
    if not manifest:
        return None
    if not manifest.get("enabled", True):
        return None
    return manifest

def get_tool_instance(name: str):
    """Load and return a runnable tool object from its entry_point.
    Safe Python import — never exec(). Returns None if it can't load."""
    manifest = get_tool(name)
    if not manifest:
        return None
    entry = manifest.get("entry_point")
    if not entry:
        print(f"[tool_registry] {name} has no entry_point — cannot load.")
        return None
    module_path, _, class_name = entry.rpartition(".")
    try:
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        return cls()
    except Exception as e:
        print(f"[tool_registry] Failed to load {name}: {e}")
        return None

def requires_approval(name: str) -> bool:
    """True if the named tool needs approval. Unknown tool = True (fail closed)."""
    manifest = get_tool(name)
    if not manifest:
        return True   # unknown tool — fail closed
    return manifest.get("permission_level") in ("write_gated", "always_gated")


# Discover on import.
_REGISTRY = _discover()