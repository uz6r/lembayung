#!/bin/bash
set -e

# Build the dev Docker image from the scripts directory
docker build -t lembayung-dev -f scripts/Dockerfile.dev .

# Run the command passed to the script inside the container
docker run --rm -v $(pwd):/app lembayung-dev "$@"
