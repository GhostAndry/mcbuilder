#!/usr/bin/env bash
# Builds the unified jar. Requires a JDK the toolchain can use (21 by default).
set -euo pipefail
cd "$(dirname "$0")"

./gradlew clean build --no-daemon "$@"
echo "[build.sh] Done — unified jar in build/libs/"
