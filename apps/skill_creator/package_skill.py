# apps/skill_creator/package_skill.py
# Zips a skill folder into a shareable .aegonskill artifact.
# The artifact can be sent to another Aegon instance and installed via install_skill.py.
#
# Usage:
#   python -m apps.skill_creator.package_skill tools/reminder
#   → skills/reminder.aegonskill

import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR   = PROJECT_ROOT / "skills"


def package_skill(skill_dir: Path) -> Path:
    if not skill_dir.is_dir():
        raise FileNotFoundError(f"Skill directory not found: {skill_dir}")

    connector_json = skill_dir / "connector.json"
    if not connector_json.exists():
        raise FileNotFoundError(f"No connector.json in {skill_dir} — not a valid skill.")

    SKILLS_DIR.mkdir(exist_ok=True)
    output_path = SKILLS_DIR / f"{skill_dir.name}.aegonskill"

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(skill_dir.rglob("*")):
            if file.is_file() and "__pycache__" not in file.parts:
                zf.write(file, file.relative_to(skill_dir.parent))

    return output_path


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m apps.skill_creator.package_skill <skill_dir>")
        print("Example: python -m apps.skill_creator.package_skill tools/reminder")
        sys.exit(1)

    skill_dir = Path(sys.argv[1]).resolve()
    try:
        output = package_skill(skill_dir)
        print(f"Packaged: {output}")
        print(f"Share this file. Install on another Aegon with:")
        print(f"  python -m apps.skill_creator.install_skill {output.name}")
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
