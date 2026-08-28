# load-targets-matrix

Composite GitHub Action that reads every target manifest in a directory into a GitHub Actions matrix, validating each one's required shape. Specialized counterpart to [`load-yaml-matrix`](../load-yaml-matrix) for `targets/*.yml` specifically — `load-yaml-matrix` stays generic and unvalidated for everything else (`vaults/*.yml`).

## Usage

```yaml
- uses: rubykatzen/flightdeck/.github/actions/load-targets-matrix@main
  id: load-targets
  with:
    # directory: targets  # optional, default shown
    # name: all           # optional; single target name to load, default: all
```

The action exposes `matrix`, containing `{ "include": [...] }`, and `count`. Each matrix item merges the manifest's own top-level YAML fields with `name` (the file's basename) and `manifest` (its path).

Every manifest must set `hosts` (non-empty list), `app_refs` (non-empty list), `apps` (non-empty object), `ssh_private_key_secret` (non-empty string - the name of the GitHub Secret holding this target's SSH private key), and `sops_age_key_secret` (non-empty string - the name of the GitHub Secret holding this target's private SOPS age key). This fails the matrix build immediately, with an error naming the specific broken target, rather than letting a malformed manifest reach `deploy/deploy.py`/`deploy/renovate.py` much later, after a checkout and dependency install on a different job entirely.

Files may use either the `.yml` or `.yaml` extension. Filenames must match `^[a-z0-9][a-z0-9-]*$` and be unique per directory; duplicate top-level YAML keys within a manifest are rejected.
