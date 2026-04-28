import os
import shutil
import subprocess
import sys
from getpass import getpass
from pathlib import Path

import bcrypt


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_FILE = ROOT / "db" / "001_init.sql"


def main() -> int:
    pin = os.environ.get("INIT_PIN")
    if not pin:
        pin = getpass("Initial local PIN: ")

    if not pin.strip():
        print("PIN cannot be empty", file=sys.stderr)
        return 1

    pin_hash = bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    sql = SCHEMA_FILE.read_text(encoding="utf-8").replace("__PIN_HASH_PLACEHOLDER__", pin_hash)

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
        ]
    else:
        database_url = os.environ.get("DATABASE_URL", "postgresql:///personal_xp_local")
        cmd = ["psql", database_url]

    result = subprocess.run(cmd, input=sql, text=True, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
