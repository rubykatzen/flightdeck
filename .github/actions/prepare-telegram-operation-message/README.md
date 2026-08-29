# prepare-telegram-operation-message

Formats a deploy or renovate result as escaped Telegram MarkdownV2. The header shows the repository and target in bold and links the operation label to its GitHub Actions run. Optional `{app, host}` items are grouped by host below the header.

```yaml
- uses: rubykatzen/flightdeck/.github/actions/prepare-telegram-operation-message@main
  id: prepare-notification
  with:
    repository: ${{ github.repository }}
    operation: renovate
    target: ${{ steps.renovate.outputs.target-name }}
    run-url: ${{ format('{0}/{1}/actions/runs/{2}', github.server_url, github.repository, github.run_id) }}
    items: ${{ steps.renovate.outputs.updated-items }}
- uses: rubykatzen/baseline/.github/actions/send-telegram-message@v0.17.0
  with:
    message: ${{ steps.prepare-notification.outputs.message }}
    telegram-bot-token: ${{ secrets.TELEGRAM_BOT_TOKEN }}
    telegram-chat-id: ${{ vars.TELEGRAM_CHAT_ID }}
    parse-mode: MarkdownV2
```

With two updated apps on one host, the rendered message is:

```text
owner/repository · renovate completed · target

root@host
• gatus
• yamtrack
```

The action truncates oversized item lists at a complete item boundary and reports how many entries were omitted, keeping the result within Telegram's 4096-character message limit.
