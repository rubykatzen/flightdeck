# load-targets

Composite GitHub Action that validates encryption configs or deployment targets and builds a GitHub Actions matrix.

## Usage

```yaml
- uses: rubykatzen/flightdeck/.github/actions/load-targets@main
  id: targets
  with:
    mode: deploy        # encrypt or deploy
    target: all         # default: all
    # directory: custom # optional; defaults to encrypt/ or targets/ based on mode
```

The action exposes `matrix`, containing `{ "include": [...] }`, and `count`. Encrypt mode validates the flat encryption schema; deploy mode validates the flat target schema.

Every file is fully validated before it is added to the matrix. Files may use either the `.yml` or `.yaml` extension, and their basename becomes the matrix target name.
