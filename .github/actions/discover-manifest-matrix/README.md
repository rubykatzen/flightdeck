# discover-manifest-matrix

Composite GitHub Action that builds a GitHub Actions strategy matrix from files matching a glob pattern.

## Usage

```yaml
- id: discover
  uses: rubykatzen/flightdeck/.github/actions/discover-manifest-matrix@main
  with:
    pattern: projects/*/*.yml   # required
```

**Output:** `matrix` — JSON object `{"manifest": ["projects/a/server.yml", ...]}`.

Fails if no files match the pattern.

## Example

```yaml
jobs:
  discover:
    runs-on: ubuntu-latest
    outputs:
      matrix: ${{ steps.discover.outputs.matrix }}
    steps:
      - uses: actions/checkout@v6
      - id: discover
        uses: rubykatzen/flightdeck/.github/actions/discover-manifest-matrix@main
        with:
          pattern: projects/*/*.yml

  publish:
    needs: discover
    strategy:
      matrix: ${{ fromJson(needs.discover.outputs.matrix) }}
    steps:
      - run: echo "${{ matrix.manifest }}"
```
