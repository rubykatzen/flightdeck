# load-vaults-matrix

Composite GitHub Action that reads every vault manifest in `vaults/` into a GitHub Actions matrix. It does no schema validation — `encrypt-env` re-parses and validates each manifest itself when it actually encrypts it. Specialized counterpart to [`load-targets-matrix`](../load-targets-matrix), which *does* validate, for `targets/*.yml` specifically.

## Usage

```yaml
- uses: rubykatzen/flightdeck/.github/actions/load-vaults-matrix@main
  id: matrix
  with:
    # directory: vaults  # optional, default shown
```

The action exposes `matrix`, containing `{ "include": [...] }`, and `count`. Each matrix item merges the manifest's own top-level YAML fields with `name` (the file's basename) and `manifest` (its path).

Files may use either the `.yml` or `.yaml` extension. Filenames must match `^[a-z0-9][a-z0-9-]*$` and be unique per directory; duplicate top-level YAML keys within a manifest are rejected. Beyond that, the parsed YAML mapping is passed through as-is — validate anything else downstream.
