#!/usr/bin/env bash
# QATAKI dev server control: start | stop | restart | status
# Kills only the uvicorn serving qataki.main on $PORT, never unrelated processes.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${QATAKI_PORT:-12288}"
HOST="${QATAKI_HOST:-0.0.0.0}"
APP="qataki.main:app"

cd "$REPO"

# PID listening on $PORT, but only if it is our qataki uvicorn.
qataki_pid() {
  local line pid
  line="$(ss -ltnpH "sport = :$PORT" 2>/dev/null)" || true
  [ -n "$line" ] || return 1
  for pid in $(echo "$line" | grep -oE 'pid=[0-9]+' | cut -d= -f2); do
    if tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | grep -q -- "$APP"; then
      echo "$pid"; return 0
    fi
  done
  return 1
}

stop() {
  local pid
  if ! pid="$(qataki_pid)"; then
    echo "nicht aktiv auf :$PORT"
    return 0
  fi
  echo "beende QATAKI (pid=$pid) auf :$PORT ..."
  pkill -TERM -P "$pid" 2>/dev/null || true
  kill  -TERM    "$pid" 2>/dev/null || true
  for _ in 1 2 3 4 5; do
    kill -0 "$pid" 2>/dev/null || { echo "beendet"; return 0; }
    sleep 1
  done
  echo "reagiert nicht -> KILL"
  pkill -KILL -P "$pid" 2>/dev/null || true
  kill  -KILL    "$pid" 2>/dev/null || true
  sleep 1
  echo "beendet"
}

start() {
  if qataki_pid >/dev/null 2>&1; then
    echo "läuft bereits auf :$PORT"
    return 1
  fi
  [ -x "$REPO/.venv/bin/python" ] || { echo "fehlt: $REPO/.venv/bin/python"; exit 1; }
  local access=(--no-access-log)
  [ "${QATAKI_ACCESS_LOG:-0}" = "1" ] && access=()
  # bench-0.2.0: aktive Shelf-Quelle (agent-core, playwright-driver) live einbinden.
  # PYTHONPATH stellt die Quelle vor die im venv installierten Kopien; --reload-dir
  # laesst uvicorn die Quellordner mitbeobachten -> Edits greifen ohne Neuinstallation.
  local SHELF; SHELF="$(cd "$REPO/../../shelf" && pwd)"
  echo "starte QATAKI auf $HOST:$PORT (--reload, live shelf) ..."
  exec env PYTHONPATH="backend:$SHELF/agent-core/src:$SHELF/playwright-driver/src:$SHELF/credentials/src" \
    "$REPO/.venv/bin/python" -m uvicorn "$APP" \
    --app-dir backend --host "$HOST" --port "$PORT" --reload \
    --reload-dir backend \
    --reload-dir "$SHELF/agent-core/src" \
    --reload-dir "$SHELF/playwright-driver/src" \
    --reload-dir "$SHELF/credentials/src" \
    --env-file .env "${access[@]}"
}

status() {
  local pid
  if pid="$(qataki_pid)"; then
    echo "aktiv auf :$PORT (pid=$pid)"
  else
    echo "nicht aktiv auf :$PORT"
  fi
}

case "${1:-restart}" in
  start)   start ;;
  stop)    stop ;;
  restart) stop; start ;;
  status)  status ;;
  *) echo "Aufruf: $0 {start|stop|restart|status}" >&2; exit 2 ;;
esac
