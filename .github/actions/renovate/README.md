# renovate

Composite GitHub Action that re-pulls and recreates one-or-more apps' containers on a target already present in the caller's own checkout, without touching versions - no new app bundle, no new vault-sourced env, no rebuilt release tree. Just `docker compose pull && docker compose up -d` per requested app, against its already-current release, on each of the target's hosts. Sibling to [`deploy`](../deploy), same shape, deliberately narrower job.

## Usage

```yaml
jobs:
  renovate:
    strategy:
      matrix: ${{ fromJson(needs.load-targets.outputs.matrix) }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: rubykatzen/flightdeck/.github/actions/renovate@main
        id: renovate
        with:
          apps: ${{ inputs.apps }}                                         # required, JSON array e.g. '["traefik","rybbit"]'
          target-manifest: ${{ matrix.manifest }}                          # required, path in this repository
          ssh-private-key: ${{ secrets[matrix.ssh_private_key_secret] }}
          # tailscale-oauth-client-id: ${{ vars.TAILSCALE_OAUTH_CLIENT_ID }}  # optional, default: unset (skip joining a tailnet)
          # tailscale-oauth-secret: ${{ secrets.TAILSCALE_OAUTH_SECRET }}    # required only if tailscale-oauth-client-id is set
      - name: Notify Telegram
        if: steps.renovate.outputs.updated == 'true'
        uses: rubykatzen/baseline/.github/actions/send-telegram-message@v0.16.1
        with:
          message: "Renovate: updated on ${{ steps.renovate.outputs.target-name }} (${{ steps.renovate.outputs.updated-hosts }})"
          telegram-bot-token: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          telegram-chat-id: ${{ secrets.TELEGRAM_CHAT_ID }}
```

Not every target runs every requested app - `renovate.py` decides that itself, from the target manifest's own `apps` mapping, and simply does nothing (never opening an SSH connection) if none of the requested apps are present. To tell whether a host's image actually changed (rather than the pull being a no-op), it compares `docker compose images -q` output before and after the pull, and exposes that as this action's own `updated`/`updated-hosts`/`target-name` outputs.

Unlike [`deploy`](../deploy) - which has no notification logic at all - this action still has none of its own either, on purpose: it only ever reports whether something changed. Sending a Telegram message (or anything else) is the *caller's* job, as a separate step reading these outputs, same as shown above - a different caller is free to wire up a different channel, or none, without forking this action.

Same checkout model as [`deploy`](../deploy): this action never checks out anything itself, it just reads `target-manifest` from whatever the caller's own preceding `actions/checkout` step already put on disk.
