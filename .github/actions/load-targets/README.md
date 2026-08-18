# load-targets

Composite GitHub Action that validates YAML files in `targets/` and builds a GitHub Actions matrix from either their `encrypt` or `deploy` sections.

## Usage

```yaml
- uses: rubykatzen/flightdeck/.github/actions/load-targets@main
  id: targets
  with:
    mode: deploy        # encrypt or deploy
    target: all         # default: all
    directory: targets  # default: targets
```

The action exposes `matrix`, containing `{ "include": [...] }`, and `count`. When `target` is `all`, files without the requested section are skipped. A specifically selected target must contain that section.

Every target is fully validated before its requested section is added to the matrix. Target files may use either the `.yml` or `.yaml` extension, and their basename becomes the target name.
