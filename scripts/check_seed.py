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
    expected = {"users=1", "categories=11"}
    actual = set(output)
    missing = expected - actual
    if missing:
        print(f"Seed check failed: missing {sorted(missing)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
