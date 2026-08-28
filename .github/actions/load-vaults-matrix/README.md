# load-vaults-matrix

Composite GitHub Action that reads every vault manifest in `vaults/` into a GitHub Actions matrix, validating each one's minimal shape. `encrypt-env` still re-parses and validates each manifest itself, in full, when it actually encrypts it - the checks here only catch a structurally broken manifest before it reaches a checkout and dependency install on a different job entirely. Sibling to [`load-targets-matrix`](../load-targets-matrix), same shape, for `targets/*.yml` instead.

## Usage

```yaml
- uses: rubykatzen/flightdeck/.github/actions/load-vaults-matrix@main
  id: matrix
  with:
    # directory: vaults  # optional, default shown
```

The action exposes `matrix`, containing `{ "include": [...] }`, and `count`. Each matrix item merges the manifest's own top-level YAML fields with `name` (the file's basename) and `manifest` (its path).

Every manifest must set `asset` (non-empty string), `keys` (non-empty list), and `env` (non-empty mapping) - just enough to catch a missing or empty section early. `encrypt-env` is what actually validates each field's shape (name patterns, source references, and so on).

Files may use either the `.yml` or `.yaml` extension. Filenames must match `^[a-z0-9][a-z0-9-]*$` and be unique per directory; duplicate top-level YAML keys within a manifest are rejected.
