#!/usr/bin/env bash
set -euo pipefail

# Run the same checks as the PR workflow.
black --check --line-length 79 gcg/ tests/
flake8 gcg/ tests/
pytest
