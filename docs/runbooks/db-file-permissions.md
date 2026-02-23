# DB File Permissions Runbook

Purpose: Ensure the SQLite database file created by the pipeline is not world-readable.

When the pipeline initializes a file-backed SQLite DB at `dados/data.db`, the code will attempt to create the file (if missing) and set its permissions to `600` (owner read/write only).

Why: Prevent accidental exposure of persisted data and reduce risk when running on multi-user systems.

Behavior:
- The permission change is best-effort; when running on filesystems or environments that do not support `chmod` (or deny it), the pipeline will continue without failing.
- CI: If your CI runs in shared runners, ensure workspace ownership is correct. Consider adding an explicit step in CI to `chmod 600 dados/data.db` after artifact creation.

Example CI step (bash):

```bash
# after tests or DB creation
if [ -f dados/data.db ]; then
  chmod 600 dados/data.db || true
fi
```

Notes:
- On Windows, `chmod` semantics differ; the code defers to OS behavior and does not error out.
- For production deployments, prefer managed databases (Postgres, MySQL) with proper access controls.
