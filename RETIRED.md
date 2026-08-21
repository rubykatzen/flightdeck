# Retired Apps

Apps removed from the active stack. Technical details are recoverable from git history. Each entry captures only the human context: why the app was dropped.

---

## watchtower

- **Retired:** 2026-08-21
- **Reason:** Redundant once the deploy pipeline itself became idempotent — every deploy already runs `docker compose pull && up -d` for every app, which re-pulls and reconciles on its own. A separate container polling for image updates added nothing except another thing needing Docker socket access on every host.
