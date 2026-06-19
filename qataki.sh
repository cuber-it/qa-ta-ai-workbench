#!/usr/bin/env bash
# Convenience wrapper: runs the QATAKI 0.1.0 server living in done/qataki-0.1.0/.
# Passes all arguments through (start | stop | restart | status).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$ROOT/done/qataki-0.1.0/qataki-server.sh" "$@"
