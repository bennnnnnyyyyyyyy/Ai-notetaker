"""Generate a PBKDF2 admin password hash without printing the password."""

import getpass

from backend.auth import hash_password


def main() -> None:
    first = getpass.getpass("Admin password: ")
    second = getpass.getpass("Repeat admin password: ")
    if not first or first != second:
        raise SystemExit("Passwords were empty or did not match.")
    print("ADMIN_PASSWORD_HASH=" + hash_password(first))


if __name__ == "__main__":
    main()
