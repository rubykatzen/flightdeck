# Changelog

## [1.0.0](https://github.com/rubykatzen/flightdeck/compare/v0.11.1...v1.0.0) (2026-08-28)


### ⚠ BREAKING CHANGES

* rework deploy/renovate as composite actions with validated targets ([#162](https://github.com/rubykatzen/flightdeck/issues/162))

### Bug Fixes

* rename dependabot label to deps, matching baseline 0.16.2 ([#175](https://github.com/rubykatzen/flightdeck/issues/175)) ([800eb86](https://github.com/rubykatzen/flightdeck/commit/800eb860fc58653a1a95e0c11151dd76dbf4ce53))


### Code Refactoring

* rework deploy/renovate as composite actions with validated targets ([#162](https://github.com/rubykatzen/flightdeck/issues/162)) ([cfd3cb7](https://github.com/rubykatzen/flightdeck/commit/cfd3cb7d170e06a54f9513cfcd5e4b391ab4b448))

## [0.11.1](https://github.com/rubykatzen/flightdeck/compare/v0.11.0...v0.11.1) (2026-08-26)


### Bug Fixes

* resolve build-apps-bundle's local action ref for external callers ([#165](https://github.com/rubykatzen/flightdeck/issues/165)) ([90a5333](https://github.com/rubykatzen/flightdeck/commit/90a5333abd6c38b15fbee62323d7ad65e490c03c))

## [0.11.0](https://github.com/rubykatzen/flightdeck/compare/v0.10.0...v0.11.0) (2026-08-25)


### Features

* let an app skip vaults entirely instead of using an empty one ([#160](https://github.com/rubykatzen/flightdeck/issues/160)) ([3940976](https://github.com/rubykatzen/flightdeck/commit/39409768f6f8ddcc6e104b8f5b13ffe28ccac4f6))

## [0.10.0](https://github.com/rubykatzen/flightdeck/compare/v0.9.0...v0.10.0) (2026-08-25)


### Features

* make a vault manifest's env: optional ([#158](https://github.com/rubykatzen/flightdeck/issues/158)) ([04b33ff](https://github.com/rubykatzen/flightdeck/commit/04b33ff12d1cfb228bf5481360b97cbc246d1815))

## [0.9.0](https://github.com/rubykatzen/flightdeck/compare/v0.8.0...v0.9.0) (2026-08-24)


### Features

* write a release manifest, stop apps removed from the desired set ([#154](https://github.com/rubykatzen/flightdeck/issues/154)) ([4b75d1d](https://github.com/rubykatzen/flightdeck/commit/4b75d1d2871ae373fafc859959ca3fa8461c6bd7))

## [0.8.0](https://github.com/rubykatzen/flightdeck/compare/v0.7.0...v0.8.0) (2026-08-24)


### Features

* support literal values in vault manifests, use for DISABLE_SIGNUP ([#150](https://github.com/rubykatzen/flightdeck/issues/150)) ([c6e7d26](https://github.com/rubykatzen/flightdeck/commit/c6e7d2646f354ea150ec6941c8960560d3e0f0af))

## [0.7.0](https://github.com/rubykatzen/flightdeck/compare/v0.6.3...v0.7.0) (2026-08-24)


### Features

* add healthchecks to cloudflared and rybbit's client ([#147](https://github.com/rubykatzen/flightdeck/issues/147)) ([e11981c](https://github.com/rubykatzen/flightdeck/commit/e11981cbbe90adc424e603eef927e0d6dc16cf37))

## [0.6.3](https://github.com/rubykatzen/flightdeck/compare/v0.6.2...v0.6.3) (2026-08-24)


### Bug Fixes

* add rybbit's missing redis dependency, stop renaming clickhouse's default user ([#145](https://github.com/rubykatzen/flightdeck/issues/145)) ([dfeb5dd](https://github.com/rubykatzen/flightdeck/commit/dfeb5dddcb2071d473cb2210b26b032e806a3402))

## [0.6.2](https://github.com/rubykatzen/flightdeck/compare/v0.6.1...v0.6.2) (2026-08-24)


### Bug Fixes

* correct APP_NAME and persistent data paths for deployed apps ([#143](https://github.com/rubykatzen/flightdeck/issues/143)) ([46b4050](https://github.com/rubykatzen/flightdeck/commit/46b4050a0726255bfaad837f0468b310f7444847))

## [0.6.1](https://github.com/rubykatzen/flightdeck/compare/v0.6.0...v0.6.1) (2026-08-24)


### Bug Fixes

* pass GH_TOKEN to deploy-shared.yml's deploy step ([#141](https://github.com/rubykatzen/flightdeck/issues/141)) ([4619a8d](https://github.com/rubykatzen/flightdeck/commit/4619a8d42ee5e55529ab64b588e36794d46f2478))

## [0.6.0](https://github.com/rubykatzen/flightdeck/compare/v0.5.0...v0.6.0) (2026-08-24)


### Features

* retire hawkeye target, deploy to heimdall instead ([#138](https://github.com/rubykatzen/flightdeck/issues/138)) ([7be54a2](https://github.com/rubykatzen/flightdeck/commit/7be54a2c84c127c9842724363e464e3727ac60ee))

## [0.5.0](https://github.com/rubykatzen/flightdeck/compare/v0.4.0...v0.5.0) (2026-08-24)


### Features

* add optional cloudflared app for Cloudflare Tunnel ingress ([#135](https://github.com/rubykatzen/flightdeck/issues/135)) ([0327336](https://github.com/rubykatzen/flightdeck/commit/0327336355c358612455dbb1bb95f8b9cd9f3bbe))

## [0.4.0](https://github.com/rubykatzen/flightdeck/compare/v0.3.0...v0.4.0) (2026-08-21)


### Features

* deploy rybbit for rubykatzen.com through flightdeck itself ([#102](https://github.com/rubykatzen/flightdeck/issues/102)) ([36b258d](https://github.com/rubykatzen/flightdeck/commit/36b258d64886ba68ba769c620fd76ca613add051))
* move apps to targets, support env_refs as a list ([#110](https://github.com/rubykatzen/flightdeck/issues/110)) ([318b90e](https://github.com/rubykatzen/flightdeck/commit/318b90ee95df9ef985982a33786c89eff5038305))
* push-based deploy - target host needs only Docker + Compose ([#115](https://github.com/rubykatzen/flightdeck/issues/115)) ([2a8ba58](https://github.com/rubykatzen/flightdeck/commit/2a8ba582f732ec1710168c25d47fcd5b545910cc))

## [0.3.0](https://github.com/rubykatzen/flightdeck/compare/v0.2.3...v0.3.0) (2026-08-18)


### Features

* add deploy-shared.yml, a reusable Tailscale-over-Ansible deploy workflow ([#91](https://github.com/rubykatzen/flightdeck/issues/91)) ([ce84d7d](https://github.com/rubykatzen/flightdeck/commit/ce84d7da31cd70b0f7288bbb8a0a2b95853bb2ca))


### Bug Fixes

* normalize CHANGELOG.md bullets to asterisks for pymarkdown MD004 ([#93](https://github.com/rubykatzen/flightdeck/issues/93)) ([46f9807](https://github.com/rubykatzen/flightdeck/commit/46f9807c0037b4180fb607df0775a12494f3f076))

## [v0.2.3] - 2026-07-31

* fix: mount postgres-18 volume at /var/lib/postgresql (#78)
* chore: remove intake-issue-clarification.yml push-model caller
* chore: add Clarification intake workflow (#76)
* chore(deps): bump https://github.com/rubykatzen/baseline
* chore(deps): bump https://github.com/rubykatzen/baseline
* chore(deps): bump https://github.com/rubykatzen/baseline
* fix: bump lint-shared to @v0.7 and pre-commit rev to v0.7.5
* fix: set dependabot schedule time to 10:00
* chore: switch pre-commit to rubykatzen/baseline, enable sync check
* ci: add explicit workflow permissions
* chore(deps): use v0.5 workflow ref
* chore: switch lint to shared workflow
* chore: scope dependabot automerge permissions
* chore: point dependabot automerge to v0.5
* chore: pin releaser workflows to v0.5
* chore(deps): bump rubykatzen/releaser from 0.4.1 to 0.5.9
* chore(deps): bump rubykatzen/releaser/.github/workflows/telegram-release-notify-shared.yml
* chore(deps): bump rubykatzen/releaser/.github/workflows/dependabot-automerge-shared.yml
* chore(deps): bump https://github.com/dupmachine/workflows

## [v0.2.2] - 2026-06-19

* chore: migrate release workflow from baseline to releaser (#51)
* chore(deps): bump https://github.com/dupmachine/workflows (#50)
* chore: replace pre-commit autoupdate workflow with Dependabot (#37)
* chore(deps): bump actions/checkout from 6 to 7 (#45)
* chore(deps): bump rubykatzen/baseline/.github/workflows/pre-commit-autoupdate-shared.yml (#48)
* chore(deps): bump rubykatzen/releaser/.github/workflows/dependabot-automerge-shared.yml (#46)
* chore(deps): bump rubykatzen/baseline from 0.0.12 to 0.5.3 (#47)
* chore(deps): bump rubykatzen/releaser/.github/workflows/telegram-release-notify-shared.yml (#49)
* docs: add portable agent message prefix (#42)
* chore: reference telegram-notify and dependabot-automerge from rubykatzen/releaser@v0.3.1

## [v0.2.1] - 2026-06-14

* chore: update baseline actions ref to v0.2.2

## [v0.2.0] - 2026-06-14

* fix: add actions: read permission to release job
* refactor: use composable baseline actions for release workflow
* switch release to workflow_dispatch + release-shared.yml
* update baseline workflow refs to -shared suffix
* resolve deploy latest refs via GitHub releases
* update license copyright
* add MIT license
* chore: update changelog for v0.0.4

## [v0.0.4] - 2026-06-13

* fix changelog trailing newline
* upload release artifact separately after create-release
* add dependabot, automerge, pre-commit autoupdate, telegram notify; pin baseline to v0.0.12
* pin baseline actions to v0.0.10
* scope generated app env files
* rename publish.yml to release.yml
* use composite lint actions from baseline
* split publish into build-bundle + create-release actions
* update baseline repo references
* update README: fix zip bundle, remove moved publish-app-bundle action
* remove local publish-app-bundle action, moved to dupmachine/workflows
* use publish-app-bundle action from dupmachine/workflows
* chore: update changelog for v0.0.3

## [v0.0.3] - 2026-06-12

* generate AI release notes and update CHANGELOG.md on publish
* move homepage from docker-apps-extra to core bundle
* update latest release target commit on each publish
