# apps/backup_keys.py
# Prints both Aegon encryption keys so Sir can store them in a password manager.
# Run whenever a key is rotated or after initial setup.
#
# Usage (from project root, venv active):
#   python -m apps.backup_keys
#
# Where to store the output:
#   - A password manager (e.g. Bitwarden) under a dedicated "Aegon Keys" entry.
#   - A separate device or encrypted vault.
#   - NEVER in this repo or any cloud-synced folder that isn't encrypted.

import os
import sys

KEYS = {
    "AEGON_TOKEN_KEY": (
        "Protects all OAuth tokens (Gmail, Spotify). "
        "Lose it → every connected service must be re-authorised."
    ),
    "AEGON_ENCRYPTION_KEY": (
        "Protects session logs and fact-extraction data. "
        "Lose it → historical session logs become unreadable."
    ),
}


def main() -> None:
    print("=" * 60)
    print("AEGON KEY BACKUP — copy these to your password manager")
    print("=" * 60)

    missing = []
    for name, description in KEYS.items():
        value = os.environ.get(name)
        print(f"\n{name}")
        print(f"  Purpose : {description}")
        if value:
            print(f"  Value   : {value}")
        else:
            print(f"  Value   : *** NOT SET — key is missing from environment ***")
            missing.append(name)

    print("\n" + "=" * 60)
    if missing:
        print(f"WARNING: {len(missing)} key(s) not found in environment: {', '.join(missing)}")
        sys.exit(1)
    else:
        print("Both keys found. Store them securely now, Sir.")


if __name__ == "__main__":
    main()
