# deploy

Composite GitHub Action that runs a push-based deploy against a target manifest already present in the caller's own checkout - resolves and downloads every release ref, decrypts and renders each app's env and config, merges the release, and pushes the finished result to each host over SSH. See the main [README](../../../README.md#automated-deploy) for the full sequence.

## Usage

```yaml
jobs:
  deploy:
    strategy:
      matrix: ${{ fromJson(needs.load-targets.outputs.matrix) }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: rubykatzen/flightdeck/.github/actions/deploy@main
        with:
          target-manifest: ${{ matrix.manifest }}                          # required, path in this repository
          ssh-private-key: ${{ secrets[matrix.ssh_private_key_secret] }}
          sops-age-key: ${{ secrets[matrix.sops_age_key_secret] }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
          # tailscale-oauth-client-id: ${{ vars.TAILSCALE_OAUTH_CLIENT_ID }}  # optional, default: unset (skip joining a tailnet)
          # tailscale-oauth-secret: ${{ secrets.TAILSCALE_OAUTH_SECRET }}    # required only if tailscale-oauth-client-id is set
          # tailscale-tags: tag:ci                                          # default: tag:ci
```

Unlike a `workflow_call` reusable workflow, this action doesn't check out anything itself - it reads `target-manifest` from whatever the caller's own preceding `actions/checkout` step already put on disk, and its own code (`deploy.py` and friends) comes along automatically via `$GITHUB_ACTION_PATH` whenever it's referenced as `owner/repo/.github/actions/deploy@ref`. This is also why there's no `target-manifest-ref` input here: if the caller needs a specific ref (e.g. a just-published release tag), it just checks out that ref itself before this step runs, the same way every other job in this repository already does.

`sops-age-key`/`ssh-private-key` are secret *values*, resolved by the caller from the target manifest's own `sops_age_key_secret`/`ssh_private_key_secret` fields (GitHub Secret *names* - see the main README's "Vaults And Targets" section) - this action never reads the manifest's credential fields itself, since it never has access to `secrets.*` by name.
