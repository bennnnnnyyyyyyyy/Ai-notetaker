"""Generate a PBKDF2 admin password hash without printing the password."""

import getpass
import sys
from pathlib import Path

# Allow `py -3 scripts\create_admin_password.py` from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.auth import hash_password


def main() -> None:
    first = getpass.getpass("Admin password: ")
    second = getpass.getpass("Repeat admin password: ")
    if not first or first != second:
        raise SystemExit("Passwords were empty or did not match.")
    print("ADMIN_PASSWORD_HASH=" + hash_password(first))


if __name__ == "__main__":
    main()
