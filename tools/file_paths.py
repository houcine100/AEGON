# tools/file_paths.py
# The ONLY folders Aegon may read or write. Edit ALLOWED_PATHS to control access.
# A path is allowed only if it sits inside one of these folders.

import os

# EDIT THIS: folders Aegon is allowed to touch. Use full (absolute) paths.
OBSIDIAN_VAULT = r"C:\Users\houci\Desktop\AI Projects\aegon\vault"

# Scratch space. Unlike the vault, this is NOT curated personal knowledge — it holds
# throwaway output such as saved research links (see core/research_notes.py).
WORKSPACE = r"C:\Users\houci\Desktop\AI Projects\aegon\workspace"

ALLOWED_PATHS = [
    WORKSPACE,
    OBSIDIAN_VAULT,
]


def is_allowed(path: str) -> bool:
    """True only if `path` is inside one of the ALLOWED_PATHS folders."""
    try:
        target = os.path.abspath(path)
    except Exception:
        return False
    for allowed in ALLOWED_PATHS:
        try:
            allowed_abs = os.path.abspath(allowed)
            if os.path.commonpath([target, allowed_abs]) == allowed_abs:
                return True
        except ValueError:
            # Different drives, etc. — not allowed.
            continue
    return False