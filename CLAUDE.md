# Shared Album Mgmt: notes for Claude and other coding agents

Home Assistant custom integration (`shared_album_mgmt`), installed through the
Marketplace on Home Assistant 2026.11 and newer and through HACS on 2026.10.
It copies public iCloud shared albums into a media folder and keeps them in
sync, with an admin-only sidebar panel. Read this before changing anything.

## Layout

- `custom_components/shared_album_mgmt/`: the integration.
  - `__init__.py`: setup and unload, services (`sync_now`, `rebuild_index`,
    `purge_quarantine`). One config entry per album; setup never waits on
    Apple (the first sync runs as a background task).
  - `links.py`: parses modern (`photos.icloud.com/shared/album/<id>`) and
    legacy (`www.icloud.com/sharedalbum/#<id>`) links.
  - `hosts.py`: the trusted-host allow-list (CloudKit, sharedstreams,
    download). Every URL Apple hands back goes through `require_trusted_url`.
  - `api.py`: `SharedAlbumClient` reads an album (CloudKit public resolve +
    partition query for modern links; sharedstreams webstream/webasseturls
    for legacy links) and opens downloads, following redirects by hand so
    each hop is checked. `RemoteAsset.choose` picks the rendition for the
    Photo format.
  - `sync.py`: `AlbumSyncer`, the engine: plan, free-space guard, downloads
    (temp file, size check, optional HEIC conversion, atomic rename),
    departures under the leave mode with the safety rules, pruning,
    `index.json`/`latest.jpg`.
  - `store.py`: per-album `Store` of asset and quarantine records.
  - `coordinator.py`: `AlbumCoordinator`, scheduling, errors to state and
    Repairs issues, progress pushes to the panel.
  - `convert.py`: pillow-heif loading and HEIC to JPEG; thumbnails.
  - `options.py`: defaults, validation and folder resolution, shared by the
    options flow and the panel.
  - `config_flow.py`: user/settings/panel/reconfigure steps, options flow
    with sections.
  - `websocket_api.py`, `thumbs.py`, `panel.py`: the panel's admin-only API,
    signed media/thumbnail view, and panel registration.
  - `catalog.py`: `albums.json` per parent folder.
  - `repairs.py`: the "trust this host" fix flow.
  - `sensor.py`, `binary_sensor.py`, `button.py`, `image.py`, `entity.py`.
  - `diagnostics.py`: redacts the link, album id and tokens.
  - `frontend/shared-album-mgmt-panel.js`: the built Lit panel (source in
    `frontend/` at the repo root; `npm run build` refreshes it).
- `frontend/`: panel source. `logic.mjs` is the part the Node tests import.
- `tests/`: pytest with `tests/fake_apple.py` (a fake aiohttp session that
  plays Apple's endpoints), plus `tests/panel.test.mjs`.
- `README.md` is user documentation; `CHANGELOG.md` is the release history.

## Checks

The shared checks below, plus `mypy custom_components/shared_album_mgmt`
(the Test workflow runs it), `node --test tests/*.mjs` for the panel logic,
and `npm run build` after changing `frontend/`. Hassfest is `python -m
script.hassfest --integration-path custom_components/shared_album_mgmt`
from a Home Assistant core checkout (it is not installed with the harness).

## Conventions

- Public albums only. No Apple ID, pyicloud or 2FA: Shared Photo Libraries
  need a signed-in session and are out of scope.
- No blocking I/O on the event loop. Every file operation goes through
  `hass.async_add_executor_job`; pillow-heif is imported once in the
  executor from `async_setup`. `tests/test_blocking_io.py` checks it.
- Never contact a host that isn't on the allow-list. New Apple hosts go in
  `hosts.py` with accept/reject tests in `tests/test_hosts.py`; users can add
  their own through Extra trusted hosts or the Repairs issue.
- Never remove a file unless: a complete listing was read before (baseline),
  the current listing isn't empty or partial, a mass removal has been seen
  twice, and the file's SHA-256 still matches what was downloaded. Restored
  files are pinned. Keep these rules and their tests together in `sync.py`
  and `tests/test_sync.py`.
- Errors are state (Last error, Problem, panel banner), never
  `UpdateFailed`/unavailable entities.
- `index.json` stays readable by iCloud Shared Album Sync's consumers
  (version 2 keys); only add keys.
- The album link is a secret: never log it, keep it out of diagnostics and
  the panel payload (the panel gets a redacted id).
- `strings.json` and `translations/en.json` are identical.
- pillow-heif is pinned in `manifest.json`, `requirements_test.txt` and
  `requirements_test_min.txt`. The org standards check matches requirement
  names with `startswith("pillow")`, so it flags pillow-heif as Pillow; that
  is a false positive until the check compares exact names.

## Open decisions

- None.

<!-- BEGIN bisman-automations shared rules -->
<!-- This block is the same in every bisman-automations repo. Edit it in
     bisman-automations/.github (templates/CLAUDE.shared.md) and copy it to
     every repo; the Validate workflow's "standards" job checks it matches. -->

## Shared rules (every bisman-automations repo)

### Releases

- The version lives in `custom_components/<domain>/manifest.json`. Anything
  else that repeats it is called out in the repo-specific notes below and is
  bumped in the same commit.
- Versions follow [Semantic Versioning](https://semver.org): patch for fixes,
  translations, docs and CI; minor for new features, options or entities;
  major when something users rely on is removed or renamed (entities,
  services, events, options) or setup has to be redone.
- Check what is released before choosing a version:
  `git ls-remote --tags origin | awk -F/ '{print $3}' | sort -V | tail -1`
  (`sort -V`: plain sorting puts `v1.10.0` before `v1.9.0`). Never add
  changes to a released version. If the manifest version has no tag yet,
  add to its CHANGELOG section instead of bumping again.
- Every push to `main` ships as a release. In that same commit, named
  `Release X.Y.Z`, bump the manifest version and write the notes directly
  under a new `## [X.Y.Z] - YYYY-MM-DD` heading in `CHANGELOG.md` (Keep a
  Changelog: Added, Changed, Deprecated, Removed, Fixed, Security), with
  that version's compare link at the bottom. There is no `## [Unreleased]`
  section and no `[Unreleased]:` compare link. New work is not collected
  under a holding heading and moved later; the release commit is where the
  heading and the entries are written. The standards check fails if a
  `## [Unreleased]` heading is present.
- Ask Donavan before every push. Push fast-forward only: never force-push,
  rebase or amend anything already pushed, or rewrite history in any other
  way. Rewriting history orphans the release tags (it broke drafting in
  ha-button-actions).
- Pushing to `main` runs **Draft release**, which creates or refreshes a
  draft `vX.Y.Z` with that version's CHANGELOG section as the notes, the
  commits since the last release and `<domain>.zip`. **Donavan publishes
  the draft himself**, and publishing creates the tag. Never create or push
  tags, publish releases, or edit published releases.
- Publishing runs **Release check**: the tag must match the manifest version
  and the CHANGELOG, and be on `main`. If it fails, fix it with a new patch
  release, not by moving the tag.

### Commits

- Author commits as `Donavan Becker <donavan.becker@icloud.com>` (set
  `git config user.name` / `user.email` in the clone). HACS's
  default-repository check needs the submitter to have a fair share of the
  commits. Credit an AI assistant with a `Co-Authored-By:` trailer if you
  like, never as the author.
- Subject lines are plain, imperative and say what changed for the user
  ("Show Pico remotes as unavailable when Lutron isn't running"). No
  `fix:`/`feat:` prefixes. Release commits are "Release X.Y.Z".
- Commit and push only when asked.

### CI (shared workflows)

- `.github/workflows/` holds four thin callers of the reusable workflows in
  [bisman-automations/.github](https://github.com/bisman-automations/.github):
  `test.yml` (lint, frontend, pytest on the oldest supported and the newest
  Home Assistant, plus the upcoming one as information only), `validate.yml`
  (hassfest, HACS, standards), `draft-release.yml` and `release-check.yml`.
  Don't add jobs to the callers. Use the shared workflow's inputs, or change
  the shared workflow so every repo gets the improvement.
- `requirements_test.txt` leaves `pytest-homeassistant-custom-component`
  unpinned (newest Home Assistant) and pins ruff (and mypy where used).
  `requirements_test_min.txt` pins the harness release for the minimum in
  `hacs.json`: the newest harness release of that month. CI fails if they
  drift apart.
- Raising the minimum Home Assistant means changing, together: `hacs.json`,
  `requirements_test_min.txt`, `python-min` in `test.yml` (3.13 up to
  2026.2, 3.14 from 2026.3), the README's Home Assistant badge, and a
  CHANGELOG entry.
- Home Assistant 2026.3 and newer need Python 3.14 (3.14.2+).
- The published hassfest rejects `categories` in `manifest.json` and Pillow
  in `requirements`. Leave both out.
- Dependabot (`.github/dependabot.yml`) proposes action and pinned-tool
  updates weekly. It ignores the test harness on purpose.
- Test and Validate also run every Thursday, the day after Home Assistant's
  betas come out. The **next** test job (newest pre-release harness) is
  information only: when it fails, fix the cause before that release ships.

### Before saying work is done

Run from the repo root, in a Python 3.14 venv with `requirements_test.txt`
installed:

```
ruff check .
ruff format --check .
pytest
```

Also run `node --test tests/*.mjs` when the repo has Node tests, mypy when
the repo-specific notes list it, and the tests in a second venv with
`requirements_test_min.txt` when a change could behave differently on the
oldest supported Home Assistant. The standards check (also in CI) is
`python <path to bisman-automations/.github>/scripts/check_repo.py .`.

### Code and docs

- Support every Home Assistant from the `hacs.json` minimum to the newest
  release. Check for deprecations in the newest release and the beta.
- Keep entity IDs, unique IDs, service names and event names stable. When
  one has to change, migrate it and say so under Changed in the CHANGELOG.
- `strings.json` and `translations/en.json` hold the same keys. Home
  Assistant reads only `translations/`, so change both in the same commit.
- Never put personal details in the repo (README, CHANGELOG, code, tests,
  screenshots): no names, addresses, account or device identifiers, or real
  entity IDs. Use placeholders such as `light.living_room`.
- `README.md` is user documentation with the standard header (badges, HACS
  and "add integration" My buttons) and sections Installation, Setup, ...,
  Troubleshooting, Development, License. Use plain language and show names,
  not entity IDs, wherever the UI does.
<!-- END bisman-automations shared rules -->
