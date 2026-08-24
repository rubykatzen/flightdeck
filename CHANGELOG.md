# Changelog

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
