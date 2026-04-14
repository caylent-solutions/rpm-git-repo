# CHANGELOG



## v1.1.0 (2026-04-14)

### Feature

* feat: resolve PEP 440 version constraints in manifest XML project revisions

feat: resolve PEP 440 version constraints in manifest XML project revisions ([`3229932`](https://github.com/caylent-solutions/rpm-git-repo/commit/32299327b1af69236eedb6e5f34e8de25fdd3256))

* feat: resolve PEP 440 version constraints in manifest XML project revisions

Manifest XML &lt;project revision&gt; attributes now support PEP 440 version
constraints (e.g., refs/tags/path/~=0.2.0, refs/tags/path/&gt;=1.0.0,&lt;2.0.0).

Previously, constraints were only supported in .kanon files where the Kanon
CLI pre-resolved them. The repo tool passed constraint strings directly to
git as ref names, which failed because constraints are not valid git refs.

The fix adds _ResolveVersionConstraint() to the Project class, which:
1. Detects PEP 440 constraints via version_constraints.is_version_constraint()
2. Resolves against remote tags via git ls-remote --tags
3. Replaces revisionExpr with the resolved exact tag ref

Called from both Sync_NetworkHalf (before any git operations) and
GetRevisionId (fallback for direct calls without prior sync).

Supported constraint operators: ~=, &gt;=, &lt;=, &gt;, &lt;, ==, !=, * (wildcard)
Range constraints: &gt;=1.0.0,&lt;2.0.0
Prefixed constraints: refs/tags/namespace/path/~=1.0.0

Also fixes pre-existing main.py formatting issue. ([`3c8dc5b`](https://github.com/caylent-solutions/rpm-git-repo/commit/3c8dc5b0a03fa6077547039cae2e70dc567b96b0))


## v1.0.1 (2026-03-30)

### Chore

* chore(release): 1.0.1 ([`e2c6203`](https://github.com/caylent-solutions/rpm-git-repo/commit/e2c62036ae1daae6831b2c6d4a4abefdaf9fcb2b))

### Fix

* fix: add caylent-platform-bot and merge commit checks to CI skip conditions

fix: add caylent-platform-bot and merge commit checks to CI skip conditions ([`2af7d04`](https://github.com/caylent-solutions/rpm-git-repo/commit/2af7d049019b5fb197b29b3b1a3b1abce3023229))

* fix: add caylent-platform-bot and merge commit checks to CI skip conditions

The release bot merge was still triggering CI workflows because:
- The merge actor is caylent-platform-bot[bot], not rpm-platform-bot[bot]
- GitHub merge commit messages use &#34;Merge pull request #N from org/release-X.Y.Z&#34;,
  not the inner &#34;chore(release):&#34; commit message

Add caylent-platform-bot[bot] to actor and PR author checks across all three
workflow files, and add /release- merge commit message detection for push events. ([`41f67ec`](https://github.com/caylent-solutions/rpm-git-repo/commit/41f67ecf18b14785dd7b400156ebcd3ea1e5bc16))

### Unknown

* Merge pull request #10 from caylent-solutions/release-1.0.1

Release 1.0.1 ([`97b74f9`](https://github.com/caylent-solutions/rpm-git-repo/commit/97b74f955edfbbf8f185dc6242881a5418417c11))


## v1.0.0 (2026-03-30)

### Breaking

* feat!: skip CI pipelines for release bot PRs and merges

feat!: skip CI pipelines for release bot PRs and merges ([`48026a6`](https://github.com/caylent-solutions/rpm-git-repo/commit/48026a64ae09f897496b8bad43606ccc292fb247))

* feat!: skip CI pipelines for release bot PRs and merges

- Add PR author and branch name checks to pr-validation.yml to skip
  release PRs created by rpm-platform-bot
- Add commit message checks to main-validation.yml to skip validation,
  CodeQL, and manual-approval jobs on release merge commits
- Add dual-event conditions to codeql-analysis.yml for both push and
  PR triggers
- Fix hardcoded version assertion in test_version_matches_pyproject to
  read version dynamically from pyproject.toml
- Clean up claude settings files

BREAKING CHANGE: CI pipeline conditions have been updated to skip
validation on release bot activity. This changes the release pipeline
behavior and requires the release branch naming convention (release-*)
and commit message convention (chore(release):) to be maintained. ([`3619e21`](https://github.com/caylent-solutions/rpm-git-repo/commit/3619e214d440d739d3d12aa3443ab2cebd8a47e8))

### Chore

* chore(release): 1.0.0 ([`116d380`](https://github.com/caylent-solutions/rpm-git-repo/commit/116d380e79920d1675f0bc07d70443dc9930f320))

### Unknown

* Merge pull request #8 from caylent-solutions/release-1.0.0

Release 1.0.0 ([`79290e0`](https://github.com/caylent-solutions/rpm-git-repo/commit/79290e0f45bcb767cb891e9fbf53004b34a553bb))


## v0.1.1 (2026-03-30)

### Chore

* chore(release): 0.1.1 ([`cb718ad`](https://github.com/caylent-solutions/rpm-git-repo/commit/cb718aded08dab75f579e14d2323520f2e43004c))

### Fix

* fix: include git_ssh proxy script in wheel package

git_ssh is referenced by ssh.py as the GIT_SSH proxy but was missing
from only-include in pyproject.toml, causing repo sync to fail when a
url.insteadOf git config rewrites HTTPS remotes to SSH.

Fixes caylent-solutions/rpm-git-repo#4 ([`0cad309`](https://github.com/caylent-solutions/rpm-git-repo/commit/0cad309b684793137c9a9301b918963bb5772029))

### Unknown

* Merge pull request #6 from caylent-solutions/release-0.1.1

Release 0.1.1 ([`7fa9888`](https://github.com/caylent-solutions/rpm-git-repo/commit/7fa9888d5b8b5c25c73c47d2fa24ec825d4b5ce0))

* Merge pull request #5 from pabdavis/fix/git-ssh-missing-from-wheel

fix: include git_ssh proxy script in wheel package ([`c08dd84`](https://github.com/caylent-solutions/rpm-git-repo/commit/c08dd842fa8d2db3a43b26d9304b7dfde0227b36))


## v0.1.0 (2026-03-16)

### Chore

* chore(release): 0.1.0 ([`b9a1c0c`](https://github.com/caylent-solutions/rpm-git-repo/commit/b9a1c0c9d70d6a8664596d0ffc8b204beab043ca))

* chore: remove python entry from .tool-versions ([`e3495d0`](https://github.com/caylent-solutions/rpm-git-repo/commit/e3495d08645fcce1bba4d0508d51f4794a01c148))

### Feature

* feat: merge linkfile exclude attribute support

Merge feat/linkfile-exclude-attribute branch. Adds optional exclude
attribute to &lt;linkfile&gt; element that accepts a comma-separated list of
immediate child names to omit when linking a directory source. When
exclude is present and src is a directory, creates dest as a real
directory with per-child symlinks instead of a single directory symlink.
Auto-skips repo-internal entries (.git, .repo*, .packages). Raises
ManifestInvalidPathError when exclude is used with a file source or
glob pattern. Updates README with linkfile exclude documentation. ([`f4496fc`](https://github.com/caylent-solutions/rpm-git-repo/commit/f4496fcb2b7abfe3ca18485a8a3dab50250b223e))

* feat: add unit tests, fix lint/format, pipx docs, and pre-commit config

- Add 90+ new test files achieving comprehensive coverage across
  subcmds, project, sync, manifest, and other modules
- Fix 281 ruff lint errors (unused imports, unused variables, duplicate
  imports, None comparisons) and reformat 92 files
- Fix 4 failing tests by mocking os.path.isdir for pipx worktree guards
- Update README with pipx install from git as recommended method
- Add .coverage-data and coverage.json to .gitignore
- Unstage accidentally committed coverage.json artifact
- Exclude requirements.json from check-json pre-commit hook (uses
  line-level comments parsed by the launcher&#39;s Requirements.from_data) ([`a86b3dc`](https://github.com/caylent-solutions/rpm-git-repo/commit/a86b3dcb4b296e6a1144dc92169824bafd1b59da))

* feat: add exclude attribute to linkfile element

When exclude is present and src is a directory, linkfile creates dest as
a real directory and individually symlinks each non-excluded immediate
child instead of creating a single symlink to the entire directory.

Repo-internal entries (.git, .repo*, .packages) are auto-skipped for
defense-in-depth. Combining exclude with glob src patterns raises an
error. ([`632d56f`](https://github.com/caylent-solutions/rpm-git-repo/commit/632d56fc257be86dbab6ccd2ed118ac6baf5f0bf))

* feat: add pipx-compatible entry point for repo CLI

Add main() public wrapper in main.py and [project.scripts] entry in
pyproject.toml so pipx can install rpm-git-repo and expose the repo
command. Without a console_scripts entry pipx reports no apps and
refuses to install the package.

Add unit tests verifying main() is callable and delegates to _Main. ([`1f2d1e4`](https://github.com/caylent-solutions/rpm-git-repo/commit/1f2d1e42b31fb9837aa42f6194c409b3ed4ad67a))

* feat: initial RPM CLI release — standalone public repo

RPM Git Repo — a multi-repository management tool for Git, built for
the RPM ecosystem. Extends the standard repo tool with:

- Environment variable substitution (repo envsubst)
- PEP 440 version constraints for manifest revisions
- Absolute path linkfile destinations
- Writable copyfiles (original permissions preserved)
- Mandatory SSH with fail-fast
- Simplified submodule handling
- Automatic latest tag detection

Includes:
- Full SDLC pipeline (PR validation, main validation, PyPI publish)
- Hatchling build system (PyPI: rpm-git-repo)
- 472 tests (unit + functional) with coverage tracking
- Ruff linting/formatting, yamllint, pre-commit hooks
- Conventional commits with python-semantic-release
- CodeQL security analysis ([`0b68a37`](https://github.com/caylent-solutions/rpm-git-repo/commit/0b68a37a7de105eefdbc83abae5ef072757ce4c8))

### Fix

* fix: skip _UpdateRepoProject when .repo/repo absent (pipx install)

When repo is installed via pipx, .repo/repo does not exist as a git
directory. _UpdateRepoProject in sync.py would fail trying to fetch
updates for the repo tool with a None remote URL.

Guard with os.path.isdir(rp.worktree) so the git-based self-update
is skipped when the tool is already running from a pipx install. ([`f7f1957`](https://github.com/caylent-solutions/rpm-git-repo/commit/f7f19578b10fc30a88a52eafdbeb0a76361227b2))

* fix: include hooks/ directory in wheel package ([`bb1724e`](https://github.com/caylent-solutions/rpm-git-repo/commit/bb1724ebc0cb1fe769e9a54b8e4e9ff8d43c23a8))

* fix: skip check_repo_rev when .repo/repo absent (pipx install)

When repo is installed via pipx, .repo/repo does not exist as a git
directory. The self-update in subcmds/init.py Execute() would fail
trying to run git operations on a path that doesn&#39;t exist.

Guard the check_repo_rev call with os.path.isdir(rp.worktree) so the
git-based self-update is skipped when the tool is already running at
the correct version from a pipx install. ([`6d37d4c`](https://github.com/caylent-solutions/rpm-git-repo/commit/6d37d4c1bdeb766199f10510b58da3b72abbd415))

* fix: include requirements.json in wheel package

subcmds/init.py calls Requirements.from_dir() which reads requirements.json
to check minimum git/python versions. Without the file in the wheel the
lookup returns None and init crashes with AttributeError. ([`ab80fe2`](https://github.com/caylent-solutions/rpm-git-repo/commit/ab80fe27008c08d456d6232c27f2ccf838a4cd09))

* fix: include repo launcher script in wheel package

wrapper.py loads the repo file at runtime to read VERSION. Without repo
in the wheel the pipx entry point crashes with FileNotFoundError when
trying to resolve Wrapper().VERSION. ([`589acf6`](https://github.com/caylent-solutions/rpm-git-repo/commit/589acf6b16c57a732301ce4ae22247d5414673ab))

* fix: inject --repo-dir and --wrapper-version in pipx entry point

_Main() requires --repo-dir and --wrapper-version which the repo launcher
script normally injects. Without them the entry point exits with
&#34;no --wrapper-version argument&#34; and &#34;no --repo-dir argument&#34;.

_FindRepoDir() walks up from cwd to locate an existing .repo directory,
falling back to cwd/.repo for fresh repo init calls. main() builds the
full argv with these required flags before delegating to _Main.

Update tests to assert all required args are injected and user args
follow the -- sentinel. ([`3e9c68e`](https://github.com/caylent-solutions/rpm-git-repo/commit/3e9c68eda0ad7fe5bf2e54c6fe1fc6d2f5501f78))

### Unknown

* Merge pull request #3 from caylent-solutions/release-0.1.0

Release 0.1.0 ([`40a4c77`](https://github.com/caylent-solutions/rpm-git-repo/commit/40a4c77eb15b8225f5a3c664eebe774023e39712))

* Merge pull request #1 from caylent-solutions/feat/initial-rpm-git-repo

feat: initial RPM CLI release ([`cdb871a`](https://github.com/caylent-solutions/rpm-git-repo/commit/cdb871a3688c70f282e1f724210738f7d1b7ca43))

* Initial commit ([`3e10af4`](https://github.com/caylent-solutions/rpm-git-repo/commit/3e10af4e48abd7d809119bb40002eff58ff52d11))
