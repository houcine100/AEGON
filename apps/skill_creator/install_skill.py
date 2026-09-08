# apps/skill_creator/install_skill.py
# Installs a .aegonskill artifact into tools/.
# Axiom 4 enforced: always forces enabled: false after extraction.
# Sir audits the code, then manually sets enabled: true.
#
# Usage:
#   python -m apps.skill_creator.install_skill skills/reminder.aegonskill

import json
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR    = PROJECT_ROOT / "tools"
SKILLS_DIR   = PROJECT_ROOT / "skills"


def install_skill(artifact_path: Path) -> str:
    if not artifact_path.exists():
        raise FileNotFoundError(f"Artifact not found: {artifact_path}")
    if artifact_path.suffix != ".aegonskill":
        raise ValueError(f"Not a .aegonskill file: {artifact_path}")

    with zipfile.ZipFile(artifact_path, "r") as zf:
        # Detect skill name from the top-level folder inside the zip.
        top_dirs = {Path(name).parts[0] for name in zf.namelist() if name}
        if len(top_dirs) != 1:
            raise ValueError("Malformed artifact: expected exactly one top-level folder.")
        skill_name = top_dirs.pop()

        target_dir = TOOLS_DIR / skill_name
        if target_dir.exists():
            raise FileExistsError(
                f"tools/{skill_name}/ already exists. "
                f"Remove it first or rename the skill."
            )

        zf.extractall(TOOLS_DIR)

    # Axiom 4 gate: force enabled: false regardless of what was in the artifact.
    connector_json_path = target_dir / "connector.json"
    if connector_json_path.exists():
        data = json.loads(connector_json_path.read_text(encoding="utf-8"))
        data["enabled"] = False
        connector_json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    return skill_name


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m apps.skill_creator.install_skill <artifact.aegonskill>")
        print("Example: python -m apps.skill_creator.install_skill skills/reminder.aegonskill")
        sys.exit(1)

    artifact = Path(sys.argv[1])
    if not artifact.is_absolute():
        artifact = PROJECT_ROOT / artifact

    try:
        skill_name = install_skill(artifact)
    except (FileNotFoundError, FileExistsError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"\nInstalled: tools/{skill_name}/")
    print(f"  enabled: false  ← Axiom 4 gate — skill is INACTIVE until you approve.")
    print(f"\nAudit checklist, Sir:")
    print(f"  1. Read tools/{skill_name}/{skill_name}_tool.py — understand what it does.")
    print(f"  2. Check permission_level in tools/{skill_name}/connector.json.")
    print(f"  3. If any credentials are needed, add them to your env and re-auth.")
    print(f"  4. Run: python -m tests.test_{skill_name}")
    print(f"  5. When satisfied: set enabled: true in tools/{skill_name}/connector.json")


if __name__ == "__main__":
    main()
