# encrypt-env

Composite GitHub Action that renders an encryption config from GitHub Secrets/Variables, encrypts it for named age recipients, and uploads `.sops.env` to an existing GitHub Release.

The release must exist before this action runs.

## Usage

```yaml
- uses: rubykatzen/flightdeck/.github/actions/encrypt-env@main
  with:
    manifest: vaults/mainframe.yml                    # required
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
env:
  DOMAIN: ${DOMAIN}      # output name: ${GitHub Secret/Variable name}
  TIMEZONE: ${TIMEZONE}
  DISABLE_SIGNUP: true   # output name: literal value, no lookup at all
```

For each name in `keys`, it loads `<keys-directory>/<name>.pub`. An `env:` value wrapped as `${NAME}` is a reference - looked up in Secrets first, then Variables, and the action fails if it resolves to neither. Any other value (a bare string, number, or boolean) is a literal, used as-is with no lookup and no way to fail on "missing." `env:` can be empty (`env: {}`) or omitted entirely for an app that needs zero vault-sourced values - it just renders an empty `.env`. The manifest has no `apps` field — app selection lives on the deploy target, not the vault; see the main README's "Vaults And Targets" section.
