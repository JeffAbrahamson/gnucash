#!/bin/bash

set -euo pipefail

apt-get update
apt-get install -y --no-install-recommends \
    curl \
    less \
    procps \
    vim

rm -rf /var/lib/apt/lists/*
