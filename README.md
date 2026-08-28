# Flightdeck - Docker Compose Deployment System

A Docker-based deployment system for containerized services, with optional extra application catalogs. No manual administration — every deploy is push-based, resolved and applied entirely from GitHub Actions. Built with Traefik reverse proxy and automatic SSL certificate management.

## Key Features

- **Core Application Set** - Essential services for routing, auth, monitoring, automation, database access, error tracking, and analytics
- **Automatic SSL Certificates** - Let's Encrypt via HTTP challenge by default, or DNS-01 through a small set of supported providers, routed through Traefik
- **Modular Architecture** - Reusable docker-compose components for easy maintenance
- **Vault-based Configuration** - Each app's env is declared, encrypted, decrypted, and rendered per app - no server-side secrets handling
- **Persistent Data Management** - Organized storage with automatic backup-friendly structure
- **Database Integration** - PostgreSQL, Redis, MongoDB, TimescaleDB pre-configured
- **Health Checks** - Built-in health monitoring for all services

## Target Server Requirements

A target server needs only:

- **Docker** >= 20.10
- **Docker Compose** >= 2.0
- SSH access for the deploy key configured in that target's `ssh_private_key_secret`

## Automated Deploy

Deployment goes through the [`deploy`](.github/actions/deploy) composite action (documented in the GitHub Actions section below) wrapping [`deploy.py`](.github/actions/deploy/deploy.py) behind one input — `target-manifest`, a path to that target's own manifest file, which the action reads itself rather than receiving `hosts`/`app_refs`/`apps` already flattened. It runs as a step inside a job the caller already checked its own repository out for, so the action needs no checkout logic of its own.

The deploy is push-based and runs entirely on the GitHub Actions runner:

1. Resolve and download every release ref (app bundles, each app's encrypted env sources).
2. Merge the app bundles into a release tree.
3. Check each app's env sources for key collisions from the still-encrypted ciphertext (SOPS's dotenv output only encrypts values, so key names are readable without decryption) — scoped to that app's own sources, not across apps.
4. Decrypt each app's env with the target's private SOPS age key (a GitHub Secret) and write it straight into that app's `.env` in the release tree.
5. Render that app's `*.tpl` config files in place, next to its `docker-compose.yml`, using the decrypted values — the same substitution `envsubst` does, run here instead of on the host.
6. Write a `manifest.json` into the release tree — resolved `app_refs`/`env_refs` (the actual tag pulled, not `@latest`) and the desired app set, no secrets.
7. Push the finished release (real `.env`, already-rendered config, the manifest, one tarball) to each host over SSH. Before switching `current`, compare the new desired app set against the previous release's `manifest.json` and `docker compose down` anything no longer desired, then switch the `current` symlink and run `docker compose pull && docker compose up -d` per app.

What gets deployed — which app bundles, which apps actually run, and which encrypted env sources feed each one — is configured declaratively per target; see "Vaults And Targets" below for the manifest format.

## Project Structure

```text
flightdeck/
├── apps/                          # Application configurations
│   ├── traefik/                  # Reverse proxy & SSL
│   ├── common.yml               # Shared service definitions
│   ├── networks.yml             # Network configuration
│   ├── postgres-17.yml, postgres-18.yml   # PostgreSQL templates
│   ├── redis-7.yml, redis-8.yml           # Redis templates
│   ├── mongodb-8.yml, mysql-8.yml         # More database templates
│   ├── clickhouse-25.4.yml, clickhouse-26.5.yml, timescale-17.yml, paradedb-17.yml, pgvector-17.yml   # Analytics/search-oriented database templates
│   ├── gotenberg-8.yml           # Document conversion template
│   └── {app-name}/              # Each app directory
│       ├── docker-compose.yml   # App configuration
│       └── *.tpl                # Optional config file templates, rendered in place at deploy time
│
├── apps-data/                     # Persistent data on the target host, not in this repo
│   ├── traefik/                 # SSL certificates (acme.json)
│   ├── postgres/                # PostgreSQL data
│   └── {app-name}/              # Each app's data that must survive across releases
│
├── .github/
│   ├── actions/
│   │   ├── build-bundle/              # Build and upload a zip bundle from given paths
│   │   ├── build-apps-bundle/          # Build and upload an apps/ catalog bundle
│   │   ├── encrypt-env/                # Encrypt a target env and upload it to a release
│   │   ├── load-vaults-matrix/          # Read vaults/ into a workflow matrix, no schema validation
│   │   ├── load-targets-matrix/         # Same, but for targets/ specifically - validates the required shape
│   │   ├── deploy/                      # Push-based deploy against a target manifest (deploy.py + friends)
│   │   │   ├── deploy.py               # Deploy entrypoint (runs on the CI runner)
│   │   │   ├── resolve.py              # owner/repo@tag[:asset] release ref resolution/download
│   │   │   ├── collisions.py           # Ciphertext-based env key collision detection
│   │   │   ├── vault.py                # SOPS decryption
│   │   │   └── render.py               # envsubst-equivalent config template rendering
│   │   └── renovate/                    # Re-pull/recreate one-or-more apps' containers (renovate.py)
│   └── workflows/
│       ├── deploy.yml                  # Manual redeploy of one target
│       ├── renovate.yml                # Manual renovate of one-or-more apps across every matching target
│       └── release.yml                 # Release Please + publish Flightdeck assets + auto-deploy
│
├── vaults/                        # Encrypted env asset configurations, one per app
└── targets/                       # Deployment targets
```

## Core Applications

| Name | Purpose |
|------|---------|
| **traefik** | Reverse proxy & SSL |
| **cloudflared** | Optional Cloudflare Tunnel into traefik |
| **semaphore** | Ansible UI & task runner |
| **twofauth** | Two-factor auth manager |
| **gatus** | Status page & health checks |
| **beszel** | Server monitoring |
| **beszel-agent** | Beszel remote agent |
| **glitchtip** | Error tracking |
| **databasus** | Database management UI |
| **rybbit** | Web analytics |

This catalog is itself published as its own release asset (`flightdeck-apps.zip`), merged at deploy time like any other entry in `app_refs`. Additional apps can live in any other repo's own `apps/`-shaped catalog, published the same way, and merged in by listing its ref alongside flightdeck's own.

## Configuration

### Environment Variables

Every app's env comes from its own vault(s), declared in that target's manifest (see "Vaults And Targets" below). A vault declares the exact final variable names an app receives, mapped to GitHub Secret/Variable names - there is no server-side prefix filtering or shared root env file. Two apps' vaults can share a source secret (e.g. both mapping `DOMAIN`) without conflict, since each app ends up with its own separate `.env`.

Variable names inside a compose file are always bare, never prefixed with the app's own name - each compose file is already scoped to one app. Whether a name is "shared" or app-specific only matters on the vault side (whether more than one app's vault maps it). See `AGENTS.md` for the full naming convention.

### Network Architecture

- **traefik** - External network for reverse proxy communication
- **internal** - Isolated network for app-to-app communication
- **databases** - Dedicated network for database services (PostgreSQL, Redis, MongoDB)

`traefik` and `databases` are created on the target host by [`deploy.py`](.github/actions/deploy/deploy.py) (derived from `apps/networks.yml`'s `external: true` entries); `internal` is created by Docker Compose itself.

## Adding a New Application

### Step 1: Create App Directory

```bash
mkdir apps/{app-name}
```

### Step 2: Create `docker-compose.yml`

```yaml
# apps/myapp/docker-compose.yml
include:
  - ../networks.yml

x-environment: &environment
  MY_VAR: ${MY_VALUE}
  ANOTHER_VAR: value

services:
  myapp:
    image: myapp:latest
    extends:
      file: ../common.yml
      service: main
    expose:
      - 8080
    labels:
      - "traefik.http.services.${APP_NAME}.loadbalancer.server.port=8080"
    environment: *environment
    volumes:
      - ${DATA_DIR}/data:/data
```

**Important**: Always use the `x-environment` anchor pattern for environment variables. This ensures consistency and reduces duplication.

### Step 3: Wire It Into a Target

Add the app to whichever target's `apps` mapping should run it, and give it a vault declaring the env it needs (`MY_VALUE` in the example above) — see "Vaults And Targets" below. There is no local way to run an app outside of a real deploy; verify a new app definition by deploying it to a real (even if disposable) target.

## Troubleshooting

There's no manual administration path, so debugging means SSHing into the target host and using Docker Compose directly from the app's own folder — no wrapper needed, `apps/{app}/` is already a complete, ready-to-run Compose project:

```bash
cd apps/app-name
docker compose logs -f          # tail logs
docker compose config           # validate/inspect the resolved config
docker ps | grep app-name       # confirm it's running
```

A few things that don't fit that one-liner:

- **Networking**: `docker network ls` / `docker network inspect traefik` to check connectivity; `docker exec -it traefik wget -q --spider http://app-name` to test an app's reachability from inside the `traefik` network.
- **SSL**: Traefik creates `apps-data/traefik/acme.json` itself on first start, with the right permissions - check its logs if certificates aren't being issued.
- **DNS**: `nslookup app-name.domain.com` if the app resolves but isn't reachable.

## Additional Resources

- [AGENTS.md](AGENTS.md) - Technical documentation for AI agents and developers
- [RETIRED.md](RETIRED.md) - Apps removed from the active stack, and why

## Similar Services

Useful as a source of ready-made Docker Compose definitions when adding a new app to this catalog, or as a reference for how to structure one:

- [Dokploy](https://dokploy.com)
- [Runtipi](https://runtipi.io)
- [Coolify](https://coolify.io)
- [Portainer](https://www.portainer.io)

## GitHub Actions

This repository provides seven composite actions under `.github/actions/` (`build-bundle`, `build-apps-bundle`, `encrypt-env`, `load-vaults-matrix`, `load-targets-matrix`, `deploy`, and `renovate`) — no reusable workflows. A reusable workflow only pays for itself when the reused thing genuinely needs its own multiple jobs or job-level config (`permissions`, `concurrency`, etc.); `deploy`/`renovate` are each a single job's worth of steps, and a composite action gets that for free without a `workflow_call` boundary's checkout/secrets ceremony (see [`deploy`](#deploy) below for what that ceremony would otherwise cost).

---

### Vaults And Targets

Files in `vaults/` describe encrypted env assets, one per app — pure secrets/config, no app selection. Files in `targets/` describe deployments, including which apps run and which vault(s) feed each one. The two collections are independent; a target links to encrypted assets explicitly through each app's own `env_refs`. Matching filenames are a convenience, not an implicit relationship.

`vaults/mainframe-traefik.yml`:

```yaml
asset: mainframe-traefik.sops.env
keys:
  - mainframe
env:
  HTTP_PORT: ${MAINFRAME_TRAEFIK_HTTP_PORT}
```

`vaults/mainframe-rybbit.yml`:

```yaml
asset: mainframe-rybbit.sops.env
keys:
  - mainframe
env:
  DOMAIN: ${MAINFRAME_DOMAIN}
  DISABLE_SIGNUP: true
```

`targets/mainframe.yml`:

```yaml
app_refs:
  - rubykatzen/flightdeck@latest
  - owner/extra-apps@latest
apps:
  traefik:
    env_refs:
      - owner/config@latest:mainframe-traefik.sops.env
  rybbit:
    env_refs:
      - owner/config@latest:mainframe-rybbit.sops.env
  beszel: {}                                        # no vault-sourced env at all
hosts:
  - deploy@app1.example.com
  - deploy@app2.example.com
path: ~/flightdeck                                # optional, default shown
ssh_private_key_secret: DEPLOY_SSH_PRIVATE_KEY
sops_age_key_secret: MAINFRAME_AGE_PRIVATE_KEY
```

`ssh_private_key_secret`/`sops_age_key_secret` are GitHub Secret *names*, never the credential values themselves - the `_secret` suffix says so explicitly, since a flat field like `sops_age_key` could otherwise read as the key material itself. `sops_age_key_secret` names the GitHub Secret holding this target's *private* age key - the one used to decrypt its vaults, matching the public key in `keys/<target>.pub` used to encrypt them. Tailscale credentials live outside the target manifest entirely (`vars.TAILSCALE_OAUTH_CLIENT_ID`/`secrets.TAILSCALE_OAUTH_SECRET`, referenced directly by the workflows below) since the tailnet is shared infrastructure, not something that varies per target.

`app_refs` and `hosts` are YAML arrays; `apps` is a mapping from app name to that app's own `env_refs` array. Each host uses the SSH `user@host` format. `app_refs` must list at least one app bundle — flightdeck's own `apps/` catalog is just another entry, not implicit. `env_refs` is optional — omit it (or leave it `[]`) for an app that genuinely needs zero vault-sourced values (e.g. `beszel` above); it still gets a `.env` with `APP_NAME`/`DATA_DIR`, just no vault is fetched or decrypted for it. Don't create a vault manifest with an empty `env:` just to satisfy this field - there's nothing to encrypt, so there's nothing to gain from one. When `env_refs` is given, it must be non-empty; [`deploy.py`](.github/actions/deploy/deploy.py) decrypts and concatenates all of an app's sources into that app's own `.env` on the runner, failing loud on any key collision — but only within that one app's own sources. Two different apps' vaults sharing a key (e.g. both declaring `DOMAIN`) is expected, since each app gets a separate `.env`.

A vault manifest's `env:` value is either `${NAME}` (a reference — look up the GitHub Secret/Variable named `NAME`) or a bare literal (any other value, used as-is with no lookup at all — see `DISABLE_SIGNUP: true` above). Use a literal for a value that's fixed for this target but isn't a secret and doesn't need a GitHub Secret/Variable to exist just to hold it.

[`load-vaults-matrix`](.github/actions/load-vaults-matrix) reads every file in `vaults/` into a matrix — it does not validate the manifest shape; `encrypt-env` re-parses and validates its own manifest from `manifest` (see "`encrypt-env`" below). Targets go through the more specific [`load-targets-matrix`](.github/actions/load-targets-matrix) instead, which *does* validate the shape above (`hosts`, `app_refs`, `apps`, `ssh_private_key_secret`, `sops_age_key_secret` all required) before a broken manifest ever reaches a checkout+dependency-install on a different job entirely. The workflows calling the [`deploy`](#deploy)/[`renovate`](#renovate) actions then pull `matrix.ssh_private_key_secret`/`matrix.sops_age_key_secret` directly, to resolve actual secret values by name.

---

### `encrypt-env`

Renders an encryption config from GitHub Secrets/Variables, encrypts it with SOPS age recipients, and uploads `.sops.env` to an existing GitHub Release. Release creation remains the calling workflow's responsibility.

```yaml
- uses: rubykatzen/flightdeck/.github/actions/encrypt-env@main
  with:
    manifest: vaults/mainframe-traefik.yml           # required
    keys-directory: keys                           # default: keys
    release-tag: latest                            # required, must already exist
    release-repo: ""                               # default: current repository
    token: ${{ secrets.GITHUB_TOKEN }}             # required
  env:
    GITHUB_SECRETS_JSON: ${{ toJson(secrets) }}
    GITHUB_VARS_JSON: ${{ toJson(vars) }}
```

Requires `contents: write` permission on the calling job.

**Manifest format:**

```yaml
asset: mainframe-traefik.sops.env
keys:
  - mainframe
env:
  HTTP_PORT: ${MAINFRAME_TRAEFIK_HTTP_PORT}   # output name: ${GitHub Secret/Variable name}
  DISABLE_SIGNUP: true                        # output name: literal value, no lookup
```

Secrets take precedence over Variables when both contain the same `${...}` reference. Every reference must resolve to an existing Secret or Variable, or the action fails; literals never fail this way since there's nothing to look up.

---

### `build-bundle`

Builds a zip archive from caller-selected paths, rejects runtime state and env files, and uploads it to an existing GitHub Release. `paths` and `bundle-name` are required — this is a generic, reusable primitive (`build-apps-bundle` below is the only current caller).

<!-- x-release-please-start-version -->

```yaml
steps:
  - uses: actions/checkout@v7
    with:
      ref: v0.11.1
  - uses: rubykatzen/flightdeck/.github/actions/build-bundle@v0.11.1
    with:
      paths: apps
      bundle-name: flightdeck-apps.zip
      release-tag: v0.11.1
      token: ${{ secrets.GITHUB_TOKEN }}
```

<!-- x-release-please-end -->

Requires `contents: write` permission on the calling job.

---

### `build-apps-bundle`

A thin defaults wrapper around `build-bundle`: `paths` defaults to `apps`, `bundle-name` defaults to `flightdeck-apps.zip`. The same action publishes flightdeck's own `apps/` catalog and any consumer repository's own app bundle.

<!-- x-release-please-start-version -->

```yaml
steps:
  - uses: actions/checkout@v7
    with:
      ref: v0.11.1
  - uses: rubykatzen/flightdeck/.github/actions/build-apps-bundle@v0.11.1
    with:
      release-tag: v0.11.1
      token: ${{ secrets.GITHUB_TOKEN }}
```

<!-- x-release-please-end -->

Requires `contents: write` permission on the calling job. `flightdeck-apps.zip` is the default asset name an `app_refs` entry resolves to when it doesn't specify an explicit `:asset-name` suffix; override `bundle-name` and use that suffix when publishing under a different filename.

---

### `deploy`

Runs [`deploy.py`](.github/actions/deploy/deploy.py) against a target manifest already present in the caller's own checkout. Intended to be used from a private consumer repository that owns both the config and secrets side (a `targets/*.yml` manifest shaped like the one above, the SSH key, encrypted `.sops.env` releases, the age private key, etc.) — this repository does not hold any deploy secrets itself. That manifest's `apps.<name>.env_refs` entries typically reference that same calling repository via `${{ github.repository }}`, since it's both the config and secrets source.

This used to be a `workflow_call` reusable workflow (`deploy-shared.yml`), which needed its own second `checkout` (`repository: job.workflow_repository, ref: job.workflow_sha`) just to get *this* repository's own `deploy.py` onto the runner, and a `target-manifest-ref` input to keep that checkout's ref in sync with whatever ref the caller had already resolved its matrix from. As a composite action, neither problem exists: `deploy.py` comes along automatically via `$GITHUB_ACTION_PATH` whenever this is referenced as `owner/repo/.github/actions/deploy@ref`, and `target-manifest` is just read from whatever the caller's own preceding `actions/checkout` step already put on disk — no second checkout, no ref to keep in sync, because there's only ever one checkout to begin with.

The interface is a single path, not flattened deploy vocabulary — the caller never re-serializes its target's `hosts`/`app_refs`/`apps`/`path` through `toJson(...)`, and `deploy.py` never receives them as separate fields; it parses and validates the manifest itself. `sops-age-key`/`ssh-private-key` are the two things that genuinely can't live in that file - secret *values*, resolved by the caller from the manifest's own `sops_age_key_secret`/`ssh_private_key_secret` fields (GitHub Secret *names*) and passed in directly. The action then resolves and downloads every ref, decrypts and renders each app's env and config, merges the release, and pushes the finished result to each host over SSH — see "Automated Deploy" above for the full sequence.

Tailscale is optional, not a dependency of this action: set `tailscale-oauth-client-id` (and the matching `tailscale-oauth-secret`) to have the runner join a tailnet as an ephemeral node before deploying. Leave both unset to skip that step entirely — e.g. when the job already runs on a self-hosted runner with network access to the hosts, or reaches them some other way.

<!-- x-release-please-start-version -->

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: rubykatzen/flightdeck/.github/actions/deploy@v0.11.1
        with:
          target-manifest: targets/mainframe.yml                          # required, path in this repository
          ssh-private-key: ${{ secrets.DEPLOY_SSH_PRIVATE_KEY }}
          sops-age-key: ${{ secrets.MAINFRAME_AGE_PRIVATE_KEY }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
          # tailscale-oauth-client-id: ${{ vars.TAILSCALE_OAUTH_CLIENT_ID }}  # optional, default: unset (skip joining a tailnet)
          # tailscale-oauth-secret: ${{ secrets.TAILSCALE_OAUTH_SECRET }}    # required only if tailscale-oauth-client-id is set
          # tailscale-tags: tag:ci                                          # default: tag:ci
```

<!-- x-release-please-end -->

The `@v0.11.1` pin on the `uses:` line only controls which ref this action's own code runs at. `target-manifest`'s own `app_refs` entries are separate and don't have to match it. <!-- x-release-please-version -->

---

### `renovate`

Re-pulls and recreates one-or-more apps' containers on a target already present in the caller's own checkout, without touching versions — no new app bundle, no new vault-sourced env, no rebuilt release tree. Just `docker compose pull && docker compose up -d` per requested app, against its already-current release, on each of the target's hosts. Sibling to [`deploy`](#deploy), same checkout-free shape, deliberately narrower job.

`apps` is a JSON array, so one run can renovate several apps at once (e.g. a nightly cron renovating `["traefik","rybbit"]` while leaving everything else alone) — pass a single-element array for the one-app case. Not every target runs every requested app; [`renovate.py`](.github/actions/renovate/renovate.py) decides that itself from the target manifest's own `apps` mapping and simply does nothing — never opening an SSH connection — if none of the requested apps are present there.

It never touches `app_refs`/`env_refs`, never re-decrypts a vault, never rebuilds the release tree; it just picks up a new image behind an existing tag. To tell whether a host's image actually changed (rather than the pull being a no-op), it compares `docker compose images -q` output before and after the pull, and reports `updated`/`updated_hosts`/`target_name` (derived from the manifest's own filename) via `$GITHUB_OUTPUT` - `updated_hosts` lists `app@host` pairs, since more than one app may have been renovated in the same run. When `updated` is `true`, the action's last step sends a Telegram message via `rubykatzen/baseline`'s generic `send-telegram-message` action (the same one `notify-telegram-release.yml`/`notify-telegram-pr.yml` use under the hood) — silent when nothing actually changed.

```yaml
jobs:
  renovate:
    needs: find-targets
    if: needs.find-targets.outputs.count != '0'
    strategy:
      matrix: ${{ fromJson(needs.find-targets.outputs.matrix) }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: rubykatzen/flightdeck/.github/actions/renovate@v0.11.0
        with:
          apps: ${{ inputs.apps }}                    # JSON array, e.g. '["traefik","rybbit"]'
          target-manifest: ${{ matrix.manifest }}
          ssh-private-key: ${{ secrets[matrix.ssh_private_key_secret] }}
          telegram-bot-token: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          telegram-chat-id: ${{ secrets.TELEGRAM_CHAT_ID }}
          # tailscale-oauth-client-id: ${{ vars.TAILSCALE_OAUTH_CLIENT_ID }}
          # tailscale-oauth-secret: ${{ secrets.TAILSCALE_OAUTH_SECRET }}
```

**Known gap:** if none of the requested `apps` match any target at all (a typo, say), every matrix job just does nothing and the whole run still reports success — there's no cheap way to fail loudly on "zero matches across the board" without a job that waits on the whole matrix and inspects its results. `apps`' "all/single/list" selection and scheduled/allowlist-driven runs (see #168) also aren't implemented yet — this only ever renovates exactly the apps it's given.

## License

Flightdeck is released under the [MIT License](LICENSE).
