# personal-xp

Personal spending tracker for Erik and Ocha.

## Local Setup

Create the virtual environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -U pip wheel
.venv/bin/pip install -r requirements.txt
```

Start local Postgres:

```bash
make db-up
```

If Docker is not installed but Homebrew Postgres is running, create a local database instead:

```bash
make db-local-create
```

Apply the schema with a runtime PIN:

```bash
INIT_PIN='<your-pin>' make migrate
```

Check seed data:

```bash
make seed-check
```

## Security Notes

- The PIN is never committed.
- The database stores only `users.pin_hash`.
- `.env`, receipt uploads, and backup dumps are ignored by git.

## Production

Production deployment is documented in the Obsidian project docs and should only happen after local sign-off.
