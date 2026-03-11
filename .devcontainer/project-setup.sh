#!/usr/bin/env bash

set -euo pipefail

# Source shared functions
source "$(dirname "$0")/devcontainer-functions.sh"

make install

log_info "Project-specific setup complete"
