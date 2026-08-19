# Flightdeck - Core Self-Hosted Application Runtime

A Docker-based orchestration system for deploying core self-hosted services, with optional extra application catalogs. Built with Traefik reverse proxy, automatic SSL certificate management, GitHub Release bundles, and a unified command-line interface.

## 🎯 Key Features

- **Core Application Set** - Essential services for routing, auth, monitoring, automation, database access, error tracking, and analytics
- **Extra Application Bundles** - Optional release app catalogs can be merged during Ansible deploy
- **Traefik Reverse Proxy** - Automatic routing, SSL/TLS termination, and certificate management
- **Automatic SSL Certificates** - Support for Cloudflare DNS and Let's Encrypt HTTP challenges
- **Modular Architecture** - Reusable docker-compose components for easy maintenance and scaling
- **Environment-based Configuration** - Three-tier configuration cascade for flexibility
- **Persistent Data Management** - Organized storage with automatic backup-friendly structure
- **Database Integration** - PostgreSQL, Redis, MongoDB, TimescaleDB pre-configured
- **Health Checks** - Built-in health monitoring for all services
- **CI/CD Ready** - GitHub Actions workflow for automatic deployment via Tailscale

## 📋 Requirements

- **Docker** >= 20.10
- **Docker Compose** >= 2.0
- **Linux/macOS/WSL2** (Windows Subsystem for Linux 2)
- **2GB+ RAM** (recommended 4GB+ for production)
- **10GB+ Storage** (depending on applications and data)

## 🚀 Quick Start

### 1. Clone and Initialize

```bash
git clone https://github.com/rubykatzen/flightdeck.git flightdeck
cd flightdeck
./up.sh
```

This will:

- Copy `.env.example` to `.env`
- Create `apps-data/` directory structure
- Create Docker networks
- Set up Traefik SSL configuration

### Release Bundle

Merging the [Release Please](https://github.com/googleapis/release-please) release PR tags `main` and publishes a deployable project bundle as a GitHub Release asset:

```text
rubykatzen/flightdeck@v1.2.3
rubykatzen/flightdeck@latest
```

In deploy refs, `@latest` is resolved through GitHub's latest release API. It is not a mutable `latest` tag or release.

The release asset is `flightdeck.zip` with the compose files and helper scripts, but not runtime state such as `.env`, `apps-data/`, or `backups/`.

Download and unpack a bundle:

```bash
tag="$(gh release view --repo rubykatzen/flightdeck --json tagName --jq .tagName)"
gh release download "$tag" --repo rubykatzen/flightdeck --pattern flightdeck.zip
unzip -q flightdeck.zip -d /opt/flightdeck/releases/latest
```

### 2. Configure Environment

Edit `.env` with your settings:

```bash
# Domain configuration
APPS_DOMAIN=...

# SSL/TLS Configuration
APPS_CERTIFICATE_RESOLVER=...
APPS_CLOUDFLARE_DNS_API_TOKEN=...

# Database
APPS_DATABASE_PASSWORD=...

# System
APPS_TIMEZONE=...
```

### Ansible Deploy

The repository includes an Ansible playbook for deploying the published Flightdeck bundle and encrypted env package:

Target servers need Docker, Docker Compose, GitHub CLI (`gh`), SOPS, and the server-local age key.

```bash
ansible-playbook ansible/deploy.yml \
  -i mainframe, \
  -u root \
  -e flightdeck_env_ref=<owner>/<secrets-repo>@latest:<server>.sops.env
```

The `flightdeck_env_ref` format is `owner/repo@tag:asset`. Use an immutable semver tag for a pinned deploy, or `@latest` to resolve GitHub's latest release at deploy time. The playbook downloads the asset, decrypts it with the server-local SOPS age key (`flightdeck_sops_age_key_file`), links shared `.env` and `apps-data` into a timestamped release, switches `current`, and runs `./deploy.sh`.

The `flightdeck_app_ref` defaults to `rubykatzen/flightdeck@latest`.

For private GitHub Releases, pass a token through the `FLIGHTDECK_GITHUB_TOKEN`
environment variable. Store it as a secret in whatever system runs this
playbook (e.g. a GitHub Actions secret when using `deploy-shared.yml` below),
not in plain configuration.

```bash
FLIGHTDECK_GITHUB_TOKEN=...
```

When `FLIGHTDECK_GITHUB_TOKEN` is set, the playbook exports it as `GH_TOKEN`
for `gh release download`. Public releases do not need this variable.

Optional extra app bundles can be merged into the release before deploy:

```bash
ansible-playbook ansible/deploy.yml \
  -i mainframe, \
  -u root \
  -e flightdeck_env_ref=<owner>/<secrets-repo>@latest:<server>.sops.env \
  -e '{"flightdeck_extra_refs":["<owner>/<extra-repo>@latest"]}'
```

Extra bundles must contain an `apps/` directory. Extra app names cannot conflict with apps from the core bundle or earlier extra bundles.

### 3. Select Applications

Edit `.env` and set `APPS` to a comma-separated app list:

```bash
APPS=traefik,gatus,beszel,semaphore,rybbit
```

### 4. Start Applications

```bash
# Start all configured apps (Traefik must be first)
./up.sh

# Or start specific apps
./up.sh traefik gatus rybbit

# View logs
./logs.sh gatus
```

All apps will be accessible at `https://{app-name}.{APPS_DOMAIN}`

> **Tip**: To allow per-server overrides for specific variables, declare fallback syntax in the app's `docker-compose.yml`: `${MYAPP_APPS_DOMAIN:-${APPS_DOMAIN}}`. Set `MYAPP_APPS_DOMAIN` in the server's `.env` to override for that app only.

## 📁 Project Structure

```text
flightdeck/
├── apps/                          # Application configurations
│   ├── traefik/                  # Reverse proxy & SSL
│   ├── common.yml               # Shared service definitions
│   ├── networks.yml             # Network configuration
│   ├── postgres.yml             # PostgreSQL template
│   ├── redis.yml                # Redis template
│   ├── mongodb.yml              # MongoDB template
│   └── {app-name}/              # Each app directory
│       ├── .env                 # Generated app-scoped variables
│       ├── docker-compose.yml   # App configuration
│       └── config/              # Optional config templates
│
├── apps-data/                     # Persistent data (git-ignored)
│   ├── traefik/                 # SSL certificates
│   ├── postgres/                # PostgreSQL data
│   └── {app-name}/              # Each app's data
│       └── ...                  # App data directories
│
├── backups/                       # Backup archives (git-ignored)
├── ansible/
│   └── deploy.yml      # Deploy published bundle and encrypted env
├── .github/
│   ├── actions/
│   │   ├── build-bundle/              # Build and upload a release bundle
│   │   ├── encrypt-env/                # Encrypt a target env and upload it to a release
│   │   └── load-yaml-matrix/            # Read a directory of YAML manifests into a workflow matrix
│   └── workflows/
│       ├── deploy-shared.yml           # Reusable deployment workflow
│       └── release.yml                 # Release Please + publish Flightdeck assets
│
├── encrypt/                       # Encrypted env asset configurations
├── targets/                       # Deployment targets
├── .env                          # All server configuration incl. APPS list (git-ignored)
├── .env.example                  # Configuration template
│
├── up.sh                         # Start applications
├── down.sh                       # Stop applications
├── restart.sh                    # Restart applications
├── logs.sh                       # View application logs
└── backup.sh                     # Backup app data
```

## 🎮 Common Commands

### Start Applications

```bash
# Start all apps defined in APPS (pulls latest images automatically)
./up.sh

# Start specific apps
./up.sh traefik gatus rybbit
```

### Stop Applications

```bash
# Stop all apps
./down.sh

# Stop specific apps
./down.sh gatus rybbit
```

### Restart Applications

```bash
# Restart all apps
./restart.sh

# Restart specific apps
./restart.sh gatus rybbit
```

### View Logs

```bash
# View logs for specific app (requires single app name)
./logs.sh gatus

# View logs with timestamps
./logs.sh rybbit
```

### Backup Applications

```bash
# Backup all apps from a remote server
./backup.sh user@server.com
```

The script stops each app one at a time, creates a zip archive, restarts it, then downloads the archive to `backups/`. Files are named `{server}-{app}-{datetime}.zip`.

## 📦 Core Applications

| Name | Purpose |
|------|---------|
| **traefik** | Reverse proxy & SSL |
| **semaphore** | Ansible UI & task runner |
| **twofauth** | Two-factor auth manager |
| **gatus** | Status page & health checks |
| **beszel** | Server monitoring |
| **beszel-agent** | Beszel remote agent |
| **glitchtip** | Error tracking |
| **databasus** | Database management UI |
| **rybbit** | Web analytics |

Additional apps can live in an optional extra catalog repo (`apps/` directory) and be merged at deploy time with `flightdeck_extra_refs`.

## ⚙️ Configuration

### Environment Variables

Variables use a scoped env model:

**1. Server env (`/.env`)**:

Contains all variables for this server: shared `APPS_*`, per-app variables, and the comma-separated `APPS` list. Deployed by Ansible from an encrypted secrets release asset.

```bash
APPS                        # Comma-separated apps to deploy on this server
APPS_DOMAIN                 # Base domain (required)
APPS_CERTIFICATE_RESOLVER   # letsencrypt or cloudflare
APPS_CLOUDFLARE_DNS_API_TOKEN   # If using Cloudflare DNS
APPS_DATABASE_PASSWORD      # PostgreSQL/MySQL password
APPS_KEY_HEX_16             # 16-byte hex key for apps
APPS_KEY_HEX_32             # 32-byte hex key for apps
APPS_KEY_HEX_64             # 64-byte hex key for apps
APPS_TIMEZONE               # System timezone (UTC, etc.)
```

**2. Generated app env (`/apps/{app}/.env`)**:

Auto-generated by `generate-env.sh` — do not edit. Contains `APP_NAME`, all shared `APPS_*` variables, and only variables beginning with the normalized app prefix.

Examples:

- `twofauth` receives `APPS_*` and `TWOFAUTH_*`
- `beszel-agent` receives `APPS_*` and `BESZEL_AGENT_*`

An app does not receive another app's env variables.

**Per-app and per-server overrides** are declared directly in each app's `docker-compose.yml` using bash fallback syntax:

```yaml
# App-specific override, falls back to server-wide value
SOME_PATH: ${MYAPP_SOME_PATH:-${APPS_SOME_PATH}}
```

Set `MYAPP_SOME_PATH` in the server's `.env` to override for that app only. App prefixes are the uppercased app directory with hyphens replaced by underscores. See `AGENTS.md` for the full naming convention.

### Network Architecture

- **traefik** - External network for reverse proxy communication
- **internal** - Isolated network for app-to-app communication
- **databases** - Dedicated network for database services (PostgreSQL, Redis, MongoDB)
- **mcp** - External network for MCP services consumed by MetaMCP

Apps are automatically connected to appropriate networks based on their needs.

## 🆕 Adding a New Application

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
      - ../../apps-data/${APP_NAME}/data:/data
```

### Step 3: Add to `.env`

Add your app to `APPS` in `.env`:

```bash
APPS=traefik,myapp
```

### Step 4: Start the App

```bash
./up.sh myapp
```

**Important**: Always use the `x-environment` anchor pattern for environment variables. This ensures consistency and reduces duplication.

## 🔍 Troubleshooting

### Container Won't Start

```bash
# Check logs
./logs.sh app-name

# Validate docker-compose configuration
docker compose --env-file ./apps/app-name/.env --env-file .env \
  -f ./apps/app-name/docker-compose.yml config

# Check network connectivity
docker network ls
docker network inspect traefik
```

### SSL Certificate Issues

```bash
# Check Traefik logs
./logs.sh traefik

# Verify ACME certificate file
ls -la apps-data/traefik/acme.json

# Ensure correct permissions
chmod 600 apps-data/traefik/acme.json

# For Cloudflare issues, verify API token is set in .env
grep APPS_CLOUDFLARE_DNS_API_TOKEN .env
```

### Application Not Accessible

1. Verify app is running: `docker ps | grep app-name`
2. Check app logs: `./logs.sh app-name`
3. Check Traefik logs: `./logs.sh traefik`
4. Verify DNS resolves: `nslookup app-name.domain.com`
5. Test internal connectivity: `docker exec -it traefik wget -q --spider http://app-name`

## 🔐 Security Best Practices

1. **Change Default Credentials** - Update passwords in `.env` and app configurations
2. **Use Strong Passwords** - Generate with: `openssl rand -base64 32`
3. **Keep Images Updated** - Run `./restart.sh` regularly (`up.sh` pulls latest images automatically)
4. **Restrict Network Access** - Use firewall rules to limit access to Traefik ports (80, 443)
5. **Enable HTTPS** - Always use HTTPS, never expose HTTP to internet
6. **Backup Data** - Regularly backup `apps-data/` directory
7. **Monitor Logs** - Review logs regularly for errors and unauthorized access attempts
8. **Update Dependencies** - Check for updates: `docker pull app:latest`

## 📚 Additional Resources

- [AGENTS.md](AGENTS.md) - Technical documentation for AI agents and developers
- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Traefik Documentation](https://doc.traefik.io/)

## 🤝 Contributing

Contributions are welcome! To add a new application:

1. Follow the "Adding a New Application" section
2. Test thoroughly with `./up.sh app-name`
3. Document any special requirements
4. Submit a pull request with the new app configuration

## 🔄 Similar Services

If you're evaluating alternatives, these projects solve a similar problem from different angles:

| Service | Website | Focus | Service Templates |
|------|---------|---------|---------|
| **flightdeck** | This repository | Git-based Docker Compose stack with reusable templates and shell scripts | [apps](./apps/) |
| **Dokploy** | [dokploy.com](https://dokploy.com) | PaaS-style deployment panel for apps, databases, and containers | [Dokploy/templates/blueprints](https://github.com/Dokploy/templates/tree/canary/blueprints) |
| **Runtipi** | [runtipi.io](https://runtipi.io) | Beginner-friendly self-hosted app store and dashboard | [runtipi/runtipi-appstore/apps](https://github.com/runtipi/runtipi-appstore/tree/master/apps) |
| **Coolify** | [coolify.io](https://coolify.io) | Self-hosted Heroku/Vercel-style platform for apps, databases, and services | [coollabsio/coolify/templates/compose](https://github.com/coollabsio/coolify/tree/v4.x/templates/compose) |

## ⚙️ GitHub Actions

This repository provides three composite actions under `.github/actions/` (`build-bundle`, `encrypt-env`, and `load-yaml-matrix`) and one reusable workflow, `deploy-shared.yml`.

---

### Encrypt Configurations And Targets

Files in `encrypt/` describe encrypted env assets. Files in `targets/` describe deployments. The two collections are independent; a deployment links to an encrypted asset explicitly through `env_ref`. Matching filenames are a convenience, not an implicit relationship.

`encrypt/mainframe.yml`:

```yaml
asset: mainframe.sops.env
keys:
  - mainframe
apps:
  - traefik
  - rybbit
env:
  APPS_DOMAIN: MAINFRAME_DOMAIN
```

`targets/mainframe.yml`:

```yaml
flightdeck_ref: rubykatzen/flightdeck@latest
env_ref: owner/config@latest:mainframe.sops.env
extra_refs:
  - owner/extra-apps@latest
hosts:
  - deploy@100.64.0.1
  - deploy@100.64.0.2
path: ~/flightdeck
sops_age_key_file: ~/.config/sops/age/keys.txt
credentials:
  variables:
    tailscale_oauth_client_id: TAILSCALE_OAUTH_CLIENT_ID
  secrets:
    ssh_private_key: DEPLOY_SSH_PRIVATE_KEY
    tailscale_oauth_secret: TAILSCALE_OAUTH_SECRET
```

Credential fields contain GitHub Variable/Secret names, never credential values. `apps`, `extra_refs`, and `hosts` are YAML arrays. Each host uses the SSH `user@host` format. The app list is rendered into the encrypted asset as a comma-separated `APPS` value.

`load-yaml-matrix` reads every file in `encrypt/` or `targets/` into a matrix — it does not validate the manifest shape. Each manifest's fields are the responsibility of whatever consumes them: `encrypt-env` re-parses and validates its own manifest from `manifest`, and the workflows calling `deploy-shared.yml` apply `path`/`keep-releases`/`sops-age-key-file` defaults and pull `credentials.secrets`/`credentials.variables` values directly from the matrix item.

---

### `encrypt-env`

Renders an encryption config from GitHub Secrets/Variables, encrypts it with SOPS age recipients, and uploads `.sops.env` to an existing GitHub Release. Release creation remains the calling workflow's responsibility.

```yaml
- uses: rubykatzen/flightdeck/.github/actions/encrypt-env@main
  with:
    manifest: encrypt/mainframe.yml                # required
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
asset: mainframe.sops.env
keys:
  - mainframe
apps:
  - traefik
  - rybbit
env:
  APPS_DOMAIN: APPS_DOMAIN         # output name: GitHub Secret/Variable name
```

Secrets take precedence over Variables when both contain the same source key. Every source key must exist or the action fails.

---

### `build-bundle`

Builds a zip archive from caller-selected paths, rejects runtime state and env files, and uploads it to an existing GitHub Release. Callers choose the archive name and contents, so the same action publishes the core `flightdeck.zip` bundle or a consumer repository's `flightdeck-extra.zip` bundle.

```yaml
steps:
  - uses: actions/checkout@v7
    with:
      ref: v1.2.3
  - uses: rubykatzen/flightdeck/.github/actions/build-bundle@v1.2.3
    with:
      paths: apps
      bundle-name: flightdeck-extra.zip
      release-tag: v1.2.3
      token: ${{ secrets.GITHUB_TOKEN }}
```

Requires `contents: write` permission on the calling job. `flightdeck-extra.zip` is the default asset name expected by `flightdeck_extra_refs`; use an explicit `:asset-name` suffix in the ref when publishing a different filename.

---

### `deploy-shared.yml`

Runs [`ansible/deploy.yml`](ansible/deploy.yml) from this repository against the caller-supplied hosts. Intended to be called from a private consumer repository that owns both the config and secrets side (SSH key, encrypted `.sops.env` releases, etc.) — this repository does not hold any deploy secrets itself. `env-ref` typically references that same calling repository via `${{ github.repository }}`, since it's both the config and secrets source.

The interface is plain deploy vocabulary, not Ansible's — callers never see `flightdeck_*` variable names or hand-write `-e` JSON; the workflow builds that internally.

Tailscale is optional, not a dependency of this workflow: set `tailscale-oauth-client-id` (and the matching `tailscale-oauth-secret`) to have the runner join a tailnet as an ephemeral node before deploying. Leave both unset to skip that step entirely — e.g. when the job already runs on a self-hosted runner with network access to the hosts, or reaches them some other way.

```yaml
jobs:
  deploy:
    uses: rubykatzen/flightdeck/.github/workflows/deploy-shared.yml@v1.2.3
    with:
      hosts: '["deploy@100.64.0.1", "deploy@100.64.0.2"]'          # required JSON array
      app-ref: rubykatzen/flightdeck@latest                          # required full release ref
      env-ref: "${{ github.repository }}@latest:<server>.sops.env"   # required
      # extra-refs: '["owner/repo@latest"]' # optional JSON array, default: []
      # path: ~/flightdeck                 # optional, default shown
      # keep-releases: 5                   # optional, default shown
      # sops-age-key-file: /home/deploy/.config/sops/age/keys.txt   # optional, default: ~/.config/sops/age/keys.txt for `user`
      tailscale-oauth-client-id: ${{ vars.TAILSCALE_OAUTH_CLIENT_ID }}  # optional, default: unset (skip joining a tailnet)
      tailscale-tags: tag:ci                                         # default: tag:ci
    secrets:
      ssh-private-key: ${{ secrets.DEPLOY_SSH_PRIVATE_KEY }}
      tailscale-oauth-secret: ${{ secrets.TAILSCALE_OAUTH_SECRET }}  # optional, required only if tailscale-oauth-client-id is set
```

The `@v1.2.3` pin on the `uses:` line only controls which ref runs the playbook mechanism itself. `app-ref` is separate and required - it is the full release ref for the bundle the playbook downloads and deploys, and does not have to match the workflow pin.

## 📝 License

This project is provided as-is for self-hosted deployment.

---

**Last Updated**: 2026
**Supported Docker Compose**: >= 2.0
**Status**: Active Development
