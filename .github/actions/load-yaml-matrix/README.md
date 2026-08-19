# load-yaml-matrix

Composite GitHub Action that reads every YAML file in a directory into a GitHub Actions matrix. It does no schema validation — callers are responsible for the shape of their own manifests.

## Usage

```yaml
- uses: rubykatzen/flightdeck/.github/actions/load-yaml-matrix@main
  id: matrix
  with:
    directory: targets  # required
    # name: all          # optional; single manifest name to load, default: all
```

The action exposes `matrix`, containing `{ "include": [...] }`, and `count`. Each matrix item merges the manifest's own top-level YAML fields with `name` (the file's basename) and `manifest` (its path).

Files may use either the `.yml` or `.yaml` extension. Filenames must match `^[a-z0-9][a-z0-9-]*$` and be unique per directory; duplicate top-level YAML keys within a manifest are rejected. Beyond that, the parsed YAML mapping is passed through as-is — validate anything else downstream.
