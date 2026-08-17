# publish-sops-env

Composite GitHub Action that renders an env manifest from GitHub Secrets/Variables, encrypts it for named age recipients, and uploads `.sops.env` as a GitHub Release asset.

The release must exist before this action runs. Create it in a dedicated job and pass the tag explicitly via `release-tag`.

## Usage

```yaml
- uses: rubykatzen/flightdeck/.github/actions/publish-sops-env@main
  with:
    manifest: projects/docker-apps/mainframe.yml   # required
    keys-directory: keys                           # default: keys
    release-tag: ${{ needs.release.outputs.tag }}  # default: manifest release_tag or repo name
    release-repo: ""                               # default: current repository
    asset-name: ""                                 # default: manifest release_asset or <stem>.sops.env
    token: ${{ secrets.GITHUB_TOKEN }}             # required
  env:
    GITHUB_SECRETS_JSON: ${{ toJson(secrets) }}
    GITHUB_VARS_JSON: ${{ toJson(vars) }}
```

The calling job requires:

```yaml
permissions:
  contents: write
```

## Manifest

```yaml
release_asset: docker-apps--mainframe.sops.env

keys:
  - mainframe

env:
  APPS_DOMAIN: APPS_DOMAIN         # output name: GitHub Secret/Variable name
  APPS_TIMEZONE: APPS_TIMEZONE
  APPS: APPS_MAINFRAME
```

For each name in `keys`, the action loads `<keys-directory>/<name>.pub`. Secrets take precedence over Variables when both contain the same source key. Every source key must resolve or the action fails.
