# encrypt-env

Composite GitHub Action that renders an encryption config from GitHub Secrets/Variables, encrypts it for named age recipients, and uploads `.sops.env` to an existing GitHub Release.

The release must exist before this action runs.

## Usage

```yaml
- uses: rubykatzen/flightdeck/.github/actions/encrypt-env@main
  with:
    manifest: encrypt/mainframe.yml                 # required
    keys-directory: keys                            # default: keys
    release-tag: ${{ needs.release.outputs.tag }}   # required, must already exist
    release-repo: ""                                # default: current repository
    token: ${{ secrets.GITHUB_TOKEN }}              # required
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
asset: mainframe.sops.env
keys:
  - mainframe
apps:
  - traefik
  - rybbit
env:
  APPS_DOMAIN: APPS_DOMAIN         # output name: GitHub Secret/Variable name
  APPS_TIMEZONE: APPS_TIMEZONE
```

The action renders `apps` as the comma-separated `APPS` dotenv value. For each name in `keys`, it loads `<keys-directory>/<name>.pub`. Secrets take precedence over Variables when both contain the same source key. Every source key must resolve or the action fails.
