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
        id: deploy
        with:
          target-manifest: ${{ matrix.manifest }}                          # required, path in this repository
          ssh-private-key: ${{ secrets[matrix.ssh_private_key_secret] }}
          sops-age-key: ${{ secrets[matrix.sops_age_key_secret] }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
          # tailscale-oauth-client-id: ${{ vars.TAILSCALE_OAUTH_CLIENT_ID }}  # optional, default: unset (skip joining a tailnet)
          # tailscale-oauth-secret: ${{ secrets.TAILSCALE_OAUTH_SECRET }}    # required only if tailscale-oauth-client-id is set
          # tailscale-tags: tag:ci                                          # default: tag:ci
      - name: Notify Telegram
        uses: rubykatzen/baseline/.github/actions/send-telegram-message@v0.17.0
        with:
          message: ${{ steps.deploy.outputs.telegram-message }}
          telegram-bot-token: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          telegram-chat-id: ${{ vars.TELEGRAM_CHAT_ID }}
          parse-mode: MarkdownV2
```

Unlike a `workflow_call` reusable workflow, this action doesn't check out anything itself - it reads `target-manifest` from whatever the caller's own preceding `actions/checkout` step already put on disk, and its own code (`deploy.py` and friends) comes along automatically via `$GITHUB_ACTION_PATH` whenever it's referenced as `owner/repo/.github/actions/deploy@ref`. This is also why there's no `target-manifest-ref` input here: if the caller needs a specific ref (e.g. a just-published release tag), it just checks out that ref itself before this step runs, the same way every other job in this repository already does.

`sops-age-key`/`ssh-private-key` are secret *values*, resolved by the caller from the target manifest's own `sops_age_key_secret`/`ssh_private_key_secret` fields (GitHub Secret *names* - see the main README's "Vaults And Targets" section) - this action never reads the manifest's credential fields itself, since it never has access to `secrets.*` by name.

`github-token` does double duty: on the runner it resolves/downloads release refs, and it's also forwarded over the same SSH connection used to push the release, to `docker login ghcr.io` on each host before `docker compose pull` - enough to pull a private image published from a different repository under the same org/user, as long as that package's own "Manage Actions access" setting grants read to this workflow's repository. That login is scoped to a throwaway `DOCKER_CONFIG` directory, removed once the pulls finish, rather than the host's default `~/.docker/config.json` - see the main README's "Automated Deploy" section.

The action prepares a successful deploy message as its `telegram-message` output, but never sends it or receives Telegram credentials. Delivery remains the caller's job, as a plain following step. Unlike `renovate`, there's no "did anything change" output to gate it on: reaching that step at all already means the `deploy` step above it succeeded, so it just runs unconditionally.
