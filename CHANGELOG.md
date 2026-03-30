# CHANGELOG



## v0.1.1 (2026-03-30)

### Fix

* fix: include git_ssh proxy script in wheel package

git_ssh is referenced by ssh.py as the GIT_SSH proxy but was missing
from only-include in pyproject.toml, causing repo sync to fail when a
url.insteadOf git config rewrites HTTPS remotes to SSH.

Fixes caylent-solutions/rpm-git-repo#4 ([`0cad309`](https://github.com/caylent-solutions/rpm-git-repo/commit/0cad309b684793137c9a9301b918963bb5772029))

### Unknown

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
