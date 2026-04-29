import subprocess
import sys
import os
import shutil


SQL = """
SET search_path TO personal_xp, public;
SELECT 'users=' || count(*) FROM users;
SELECT 'categories=' || count(*) FROM categories;
"""


def main() -> int:
    if shutil.which("docker"):
        cmd = [
            "docker",
            "exec",
            "-i",
            "personal-xp-db",
            "psql",
            "-U",
            "postgres",
            "-d",
            "personal_xp_local",
            "-t",
            "-A",
        ]
    else:
        database_url = os.environ.get("DATABASE_URL", "postgresql:///personal_xp_local")
        cmd = ["psql", database_url, "-t", "-A"]
    result = subprocess.run(cmd, input=SQL, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode

    output = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    print("\n".join(output))

    values = {}
    for line in output:
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key] = int(value)

    if values.get("users") != 1:
        print("Seed check failed: expected exactly one shared user", file=sys.stderr)
        return 1
    if values.get("categories", 0) < 11:
        print("Seed check failed: expected at least 11 default categories", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
