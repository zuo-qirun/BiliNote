"""Operator-only account role management.

Examples:
    python scripts/account_admin.py list
    python scripts/account_admin.py set-role my_account admin
"""

import argparse

from app.services.account_access import ROLE_LABELS, account_db


def list_users() -> None:
    with account_db() as connection:
        for row in connection.execute(
            "SELECT id, username, email, role, created_at FROM accounts ORDER BY id"
        ):
            print(
                f"{row['id']:>4}  {row['username']:<32} "
                f"{ROLE_LABELS.get(row['role'], row['role']):<8} {row['email'] or '-'}"
            )


def set_role(username: str, role: str) -> None:
    with account_db() as connection:
        cursor = connection.execute(
            "UPDATE accounts SET role = ? WHERE username_key = ?",
            (role, username.strip().casefold()),
        )
        if cursor.rowcount != 1:
            raise SystemExit(f"Account not found: {username}")
    print(f"{username} -> {ROLE_LABELS[role]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    role_parser = subparsers.add_parser("set-role")
    role_parser.add_argument("username")
    role_parser.add_argument("role", choices=tuple(ROLE_LABELS))
    args = parser.parse_args()

    if args.command == "list":
        list_users()
    else:
        set_role(args.username, args.role)


if __name__ == "__main__":
    main()
