# RPM Git Repo

A multi-repository management tool for Git, built for the RPM ecosystem. RPM Git Repo extends the standard `repo` tool with environment variable templating, semantic version constraints, and enhanced linkfile support.

## Table of Contents

- [Key Features](#key-features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Feature Reference](#feature-reference)
  - [Environment Variable Substitution](#environment-variable-substitution)
  - [PEP 440 Version Constraints](#pep-440-version-constraints)
  - [Absolute Path Linkfiles](#absolute-path-linkfiles)
- [Common Commands](#common-commands)
- [Development Environment](#development-environment)
- [Local Development Setup](#local-development-setup)
- [Contributing](#contributing)
- [License](#license)

## Key Features

- **Environment Variable Substitution** (`repo envsubst`) -- template manifest XML files with `${VAR}` syntax, replacing placeholders with environment variable values at initialization time
- **PEP 440 Version Constraints** -- use fuzzy version specifiers like `~=1.2.0`, `>=1.0,<2.0`, or `*` wildcards instead of exact revisions in manifest `<project>` elements
- **Absolute Path Linkfile Destinations** -- `<linkfile>` `dest` attribute supports absolute paths, enabling symlinks anywhere on the filesystem (not just relative to the repo root)
- **Writable Copyfiles** -- copied files retain their original permissions instead of being forced read-only
- **Mandatory SSH** -- fails fast with a clear error message if SSH is not installed, instead of silently skipping SSH operations
- **Simplified Submodule Handling** -- streamlined submodule initialization without retry/backoff complexity
- **Automatic Version Detection** -- the `repo` launcher automatically detects and uses the latest release tag from GitHub

## Installation

### Quick Start (Recommended)

Install directly from the repository using [pipx](https://pipx.pypa.io/):

```bash
pipx install git+https://github.com/caylent-solutions/rpm-git-repo.git@main
```

### Production (Pinned Version)

For production environments, pin to a specific version:

```bash
pipx install rpm-git-repo==0.1.0
```

> **Note:** PyPI installs (`pipx install rpm-git-repo`) will be available after the first published release.

## Quick Start

```bash
# Initialize a repo workspace
repo init -u <YOUR_MANIFEST_URL> --no-repo-verify

# Sync all projects
repo sync
```

During `repo init`, the tool automatically fetches and uses the latest release tag from GitHub.

### Override Version

To use a specific version or branch:

```bash
repo init -u <YOUR_MANIFEST_URL> --repo-rev=0.1.0 --no-repo-verify
```

## Feature Reference

### Environment Variable Substitution

Replace `${VARIABLE}` placeholders in manifest XML files with environment variable values:

```xml
<!-- Before: manifest.xml with placeholders -->
<manifest>
  <remote name="origin"
          fetch="${GITBASE}"
          revision="${GITREV}"/>
  <project name="my-project"
           path="projects/my-project"
           remote="origin"/>
</manifest>
```

```bash
# Set environment variables
export GITBASE=https://github.com/myorg
export GITREV=main

# Run envsubst to replace variables
repo envsubst
```

```xml
<!-- After: manifest.xml with resolved values -->
<manifest>
  <remote name="origin"
          fetch="https://github.com/myorg"
          revision="main"/>
  <project name="my-project"
           path="projects/my-project"
           remote="origin"/>
</manifest>
```

The command processes all XML files under `.repo/manifests/**/*.xml`, replacing `${VAR}` placeholders in both attribute values and text content. Original files are backed up with a `.bak` extension.

### PEP 440 Version Constraints

Use version constraint syntax in manifest `<project>` revision attributes instead of exact version strings. The tool resolves constraints against available tags at sync time and selects the highest matching version.

**Supported operators:**

| Operator | Example | Meaning |
|----------|---------|---------|
| `~=` | `~=1.2.0` | Compatible release (>=1.2.0, <1.3.0) |
| `>=` | `>=1.0.0` | Greater than or equal |
| `<=` | `<=2.0.0` | Less than or equal |
| `>` | `>1.0.0` | Greater than |
| `<` | `<2.0.0` | Less than |
| `==` | `==1.2.3` | Exact match |
| `!=` | `!=1.2.3` | Not equal |
| `*` | `*` | Any version (wildcard) |

**Range constraints** (multiple specifiers joined by comma):

```xml
<project name="my-lib"
         path="libs/my-lib"
         revision="refs/tags/dev/python/my-lib/>=1.0.0,<2.0.0"/>
```

**Example with compatible release:**

```xml
<project name="quality-agent"
         path="agents/quality"
         revision="refs/tags/dev/python/quality-agent/~=1.2.0"/>
```

This resolves to the highest `1.2.x` tag available (e.g., `refs/tags/dev/python/quality-agent/1.2.7`).

### Absolute Path Linkfiles

The `<linkfile>` element supports absolute paths for the `dest` attribute, enabling symlinks to be created at any filesystem location:

```xml
<project name="shared-config" path="config">
  <!-- Absolute path: symlink created at /etc/myapp/config.yml -->
  <linkfile src="config.yml" dest="/etc/myapp/config.yml"/>

  <!-- Relative path (standard): symlink relative to repo root -->
  <linkfile src="README.md" dest="docs/config-readme.md"/>
</project>
```

Parent directories are created automatically for absolute paths. Path traversal (`..` components) is rejected for security.

### Linkfile Exclude Attribute

When the optional `exclude` attribute is present and `src` is a directory, `<linkfile>` creates `dest` as a real directory and individually symlinks each non-excluded immediate child of `src` into `dest`, instead of creating a single directory symlink.

The `exclude` value is a comma-separated list of immediate child names to omit (exact match, no globs). Using `exclude` with a file source or glob pattern raises an error.

```xml
<project name="shared-tools" path="tools">
  <!-- Link directory contents, excluding tests and docs -->
  <linkfile src="cli-agent"
            dest="marketplace/cli-agent"
            exclude="tests,docs,__pycache__"/>
</project>
```

Repo-internal entries (`.git`, `.repo*`, `.packages`) are always auto-excluded when `exclude` is active.

## Common Commands

| Command | Description |
|---------|-------------|
| `repo init -u <url>` | Initialize a new repo workspace |
| `repo sync` | Sync all projects to their specified revisions |
| `repo envsubst` | Replace `${VAR}` placeholders in manifest XML files |
| `repo forall -c <cmd>` | Run a command in every project |
| `repo status` | Show working tree status across all projects |
| `repo branches` | Show all branches across projects |
| `repo info` | Show manifest information |
| `repo help <cmd>` | Show help for a specific command |

## Development Environment

### Caylent Devcontainer (Recommended)

The fastest way to get started is using the Caylent Devcontainer, which provides a fully configured development environment with all tools pre-installed.

**Prerequisites:**
- [VS Code](https://code.visualstudio.com/) or [Cursor](https://cursor.sh/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop)
- Python 3.12+ on your host (for the CLI tool)

**Setup:**

1. Install the Caylent Devcontainer CLI:
   ```bash
   pipx install caylent-devcontainer-cli
   ```

2. Set up the devcontainer in this project:
   ```bash
   cdevcontainer setup-devcontainer /path/to/rpm-git-repo
   ```

3. Launch your IDE with the devcontainer:
   ```bash
   # VS Code (default)
   cdevcontainer code /path/to/rpm-git-repo

   # Cursor
   cdevcontainer code /path/to/rpm-git-repo --ide cursor
   ```

The devcontainer automatically runs `make install` via `project-setup.sh` on first launch, installing all development dependencies.

**Template system:** Use `cdevcontainer template create <name>` to save your environment configuration (Git credentials, AWS profiles, etc.) for reuse across projects. Load templates with `cdevcontainer template load <name>`.

For full documentation on the Caylent Devcontainer CLI, templates, AWS configuration, and CI/CD support, see the [Caylent Devcontainer documentation](https://github.com/caylent-solutions/devcontainer).

## Local Development Setup

If you prefer to develop without the devcontainer:

1. Clone the repository:
   ```bash
   git clone https://github.com/caylent-solutions/rpm-git-repo.git
   cd rpm-git-repo
   ```

2. Install development dependencies:
   ```bash
   make install-dev
   ```

3. Set up git hooks:
   ```bash
   make install-hooks
   ```

4. Run tests to verify your setup:
   ```bash
   make test
   ```

### Makefile Targets

```bash
make help             # Show all available targets
make install-dev      # Install development dependencies
make install-hooks    # Install pre-commit and pre-push hooks
make lint             # Run all lint checks
make format           # Auto-format Python files
make test             # Run full test suite with coverage
make test-unit        # Run unit tests only
make test-functional  # Run functional tests only
make validate         # Full CI equivalent: lint + test
make build            # Build the package
make publish          # Build + check distribution
make clean            # Remove build artifacts and caches
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines, commit conventions, testing requirements, and the pull request process.

## CI/CD Pipeline

The project uses a fully automated release pipeline:

1. **PR Validation** -- lint, build, unit tests (90% coverage threshold), functional tests, CodeQL security analysis
2. **Main Branch Validation** -- runs on merge to main, triggers semantic release
3. **QA Approval Gate** -- manual approval required before release
4. **Automated Release** -- `python-semantic-release` computes version from conventional commits, updates changelog, creates tag, triggers PyPI publish
5. **PyPI Publishing** -- OIDC trusted publishing (no API keys)

Version bumps are driven by PR titles using [Conventional Commits](https://www.conventionalcommits.org/):
- `feat: ...` -- Minor bump (0.1.0 -> 0.2.0)
- `fix: ...` -- Patch bump (0.1.0 -> 0.1.1)
- `feat!: ...` -- Major bump (0.1.0 -> 1.0.0)

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.
