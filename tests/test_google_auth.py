# tests/test_google_auth.py
# Re-runs the Google (Gmail + Calendar) OAuth and prints the granted scopes.
# Run from the project root with the venv active:
#   python -m tests.test_google_auth
# Use this whenever SCOPES change in core/security/gmail_auth.py — it forces a
# clean re-auth so new scopes actually take, then confirms what Google granted.

from core.security import token_store
from core.security.gmail_auth import authorize_gmail, SCOPES


def main() -> None:
    print("Requested SCOPES:")
    for scope in SCOPES:
        print(f"  - {scope}")

    # Clean re-auth: drop the old token so the new scope set is granted fresh.
    token_store.delete_token("gmail")
    authorize_gmail()

    data = token_store.load_token("gmail") or {}
    granted = data.get("scopes", [])

    print("\nGranted scopes:")
    for scope in granted:
        print(f"  - {scope}")

    missing = [s for s in SCOPES if s not in granted]
    if missing:
        print("\nWARNING — these requested scopes were NOT granted:")
        for scope in missing:
            print(f"  - {scope}")
    else:
        print("\nAll requested scopes granted.")


if __name__ == "__main__":
    main()
