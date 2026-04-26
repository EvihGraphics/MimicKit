#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/schedule_case_longcycle_resume.sh \
    --root-out <name-or-path> \
    [--after-hours <N> | --resume-at "YYYY-mm-dd HH:MM:SS"] \
    [options...]

Core options:
  --root-out <v>               Required. run_case_longcycle --root-out value.
  --after-hours <v>            Resume after N hours (supports float, e.g. 5 or 0.5).
  --resume-at <v>              Absolute resume time parsed by `date -d`.

Training options (forwarded to run_case_longcycle.py):
  --engine-config <v>          Default: data/engines/newton_engine.yaml
  --devices-train <v>          Default: cuda:0,cuda:1
  --include-nontrainable       Default: enabled
  --exclude-nontrainable       Disable include-nontrainable
  --long-mode <v>              Default: time_budget
  --long-budget-hours <v>      Default: 8
  --long-budget-signal <v>     Default: SIGINT
  --long-budget-grace-sec <v>  Default: 300
  --long-success-policy <v>    Default: budget_checkpoint
  --resume-skip-status <v>     Default: ok

Runtime options:
  --conda-sh <v>               Default: /root/miniconda3/etc/profile.d/conda.sh
  --conda-env <v>              Default: mimickit
  --workdir <v>                Default: /root/Project/MimicKit
  --main-log <v>               Default: /tmp/<root-slug>.longcycle.log
  --resume-log <v>             Default: /tmp/<root-slug>.resume.log
  --watchdog-log <v>           Default: /tmp/<root-slug>.watchdog.log
  --watchdog-interval-sec <v>  Default: 180
  --session-prefix <v>         Default: mk_longcycle
  --kill-prefix <v>            Optional. kill existing tmux sessions with this prefix.

Examples:
  # Resume in 5 hours
  scripts/schedule_case_longcycle_resume.sh \
    --root-out case_ultralong_8h_20260305_172436 \
    --after-hours 5 \
    --main-log /tmp/case_ultralong_8h_20260305_172436.log \
    --kill-prefix mk_8to24_

  # Resume at fixed time
  scripts/schedule_case_longcycle_resume.sh \
    --root-out case_ultralong_8h_20260305_172436 \
    --resume-at "2026-03-07 07:30:00" \
    --main-log /tmp/case_ultralong_8h_20260305_172436.log
EOF
}

ROOT_OUT=""
AFTER_HOURS=""
RESUME_AT=""

ENGINE_CONFIG="data/engines/newton_engine.yaml"
DEVICES_TRAIN="cuda:0,cuda:1"
INCLUDE_NONTRAINABLE=1
LONG_MODE="time_budget"
LONG_BUDGET_HOURS="8"
LONG_BUDGET_SIGNAL="SIGINT"
LONG_BUDGET_GRACE_SEC="300"
LONG_SUCCESS_POLICY="budget_checkpoint"
RESUME_SKIP_STATUS="ok"

CONDA_SH="/root/miniconda3/etc/profile.d/conda.sh"
CONDA_ENV="mimickit"
WORKDIR="/root/Project/MimicKit"

MAIN_LOG=""
RESUME_LOG=""
WATCHDOG_LOG=""
WATCHDOG_INTERVAL_SEC="180"
SESSION_PREFIX="mk_longcycle"
declare -a KILL_PREFIXES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root-out) ROOT_OUT="$2"; shift 2 ;;
    --after-hours) AFTER_HOURS="$2"; shift 2 ;;
    --resume-at) RESUME_AT="$2"; shift 2 ;;

    --engine-config) ENGINE_CONFIG="$2"; shift 2 ;;
    --devices-train) DEVICES_TRAIN="$2"; shift 2 ;;
    --include-nontrainable) INCLUDE_NONTRAINABLE=1; shift 1 ;;
    --exclude-nontrainable) INCLUDE_NONTRAINABLE=0; shift 1 ;;
    --long-mode) LONG_MODE="$2"; shift 2 ;;
    --long-budget-hours) LONG_BUDGET_HOURS="$2"; shift 2 ;;
    --long-budget-signal) LONG_BUDGET_SIGNAL="$2"; shift 2 ;;
    --long-budget-grace-sec) LONG_BUDGET_GRACE_SEC="$2"; shift 2 ;;
    --long-success-policy) LONG_SUCCESS_POLICY="$2"; shift 2 ;;
    --resume-skip-status) RESUME_SKIP_STATUS="$2"; shift 2 ;;

    --conda-sh) CONDA_SH="$2"; shift 2 ;;
    --conda-env) CONDA_ENV="$2"; shift 2 ;;
    --workdir) WORKDIR="$2"; shift 2 ;;
    --main-log) MAIN_LOG="$2"; shift 2 ;;
    --resume-log) RESUME_LOG="$2"; shift 2 ;;
    --watchdog-log) WATCHDOG_LOG="$2"; shift 2 ;;
    --watchdog-interval-sec) WATCHDOG_INTERVAL_SEC="$2"; shift 2 ;;
    --session-prefix) SESSION_PREFIX="$2"; shift 2 ;;
    --kill-prefix) KILL_PREFIXES+=("$2"); shift 2 ;;

    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "$ROOT_OUT" ]]; then
  echo "--root-out is required" >&2
  usage
  exit 2
fi
if [[ -n "$AFTER_HOURS" && -n "$RESUME_AT" ]]; then
  echo "Use exactly one of --after-hours or --resume-at" >&2
  exit 2
fi
if [[ -z "$AFTER_HOURS" && -z "$RESUME_AT" ]]; then
  echo "Missing schedule time: provide --after-hours or --resume-at" >&2
  exit 2
fi

ROOT_SLUG="$(echo "$ROOT_OUT" | tr '/:' '__' | tr -cd '[:alnum:]_-')"
if [[ -z "$ROOT_SLUG" ]]; then
  ROOT_SLUG="longcycle"
fi

if [[ -z "$MAIN_LOG" ]]; then
  MAIN_LOG="/tmp/${ROOT_SLUG}.longcycle.log"
fi
if [[ -z "$RESUME_LOG" ]]; then
  RESUME_LOG="/tmp/${ROOT_SLUG}.resume.log"
fi
if [[ -z "$WATCHDOG_LOG" ]]; then
  WATCHDOG_LOG="/tmp/${ROOT_SLUG}.watchdog.log"
fi

NOW_TS="$(date +%s)"
if [[ -n "$AFTER_HOURS" ]]; then
  SLEEP_SEC="$(awk "BEGIN { printf \"%d\", (${AFTER_HOURS}) * 3600 }")"
  if [[ "$SLEEP_SEC" -le 0 ]]; then
    echo "--after-hours must be > 0" >&2
    exit 2
  fi
  TARGET_TS="$((NOW_TS + SLEEP_SEC))"
else
  TARGET_TS="$(date -d "$RESUME_AT" +%s)"
  SLEEP_SEC="$((TARGET_TS - NOW_TS))"
  if [[ "$SLEEP_SEC" -le 0 ]]; then
    echo "--resume-at must be in the future" >&2
    exit 2
  fi
fi

TARGET_FMT="$(date -d "@${TARGET_TS}" '+%F %T %Z')"

RUNNER_SCRIPT="/tmp/${SESSION_PREFIX}_runner_${ROOT_SLUG}.sh"
RESUME_SCRIPT="/tmp/${SESSION_PREFIX}_autoresume_${ROOT_SLUG}.sh"
WATCHDOG_SCRIPT="/tmp/${SESSION_PREFIX}_watchdog_${ROOT_SLUG}.sh"
WAKE_FLAG="/tmp/${SESSION_PREFIX}_${ROOT_SLUG}.wake_once"

RESUME_SESSION="${SESSION_PREFIX}_resume_${ROOT_SLUG}"
WATCHDOG_SESSION="${SESSION_PREFIX}_watchdog_${ROOT_SLUG}"

if tmux ls >/dev/null 2>&1; then
  tmux kill-session -t "$RESUME_SESSION" 2>/dev/null || true
  tmux kill-session -t "$WATCHDOG_SESSION" 2>/dev/null || true

  for prefix in "${KILL_PREFIXES[@]}"; do
    while read -r s; do
      [[ -n "$s" ]] || continue
      tmux kill-session -t "$s" 2>/dev/null || true
    done < <(tmux ls 2>/dev/null | awk -F: -v p="$prefix" '$1 ~ ("^" p) { print $1 }')
  done
fi

rm -f "$WAKE_FLAG"

{
  echo "#!/usr/bin/env bash"
  echo "set -euo pipefail"
  echo "source \"$CONDA_SH\""
  echo "conda activate \"$CONDA_ENV\""
  echo "cd \"$WORKDIR\""
  echo "python -u scripts/run_case_longcycle.py \\"
  echo "  --engine-config \"$ENGINE_CONFIG\" \\"
  echo "  --devices-train \"$DEVICES_TRAIN\" \\"
  if [[ "$INCLUDE_NONTRAINABLE" == "1" ]]; then
    echo "  --include-nontrainable \\"
  fi
  echo "  --long-mode \"$LONG_MODE\" \\"
  echo "  --long-budget-hours \"$LONG_BUDGET_HOURS\" \\"
  echo "  --long-budget-signal \"$LONG_BUDGET_SIGNAL\" \\"
  echo "  --long-budget-grace-sec \"$LONG_BUDGET_GRACE_SEC\" \\"
  echo "  --long-success-policy \"$LONG_SUCCESS_POLICY\" \\"
  echo "  --root-out \"$ROOT_OUT\" \\"
  echo "  --resume-skip-status \"$RESUME_SKIP_STATUS\""
} > "$RUNNER_SCRIPT"
chmod +x "$RUNNER_SCRIPT"

cat > "$RESUME_SCRIPT" <<EOF
#!/usr/bin/env bash
set -euo pipefail
echo "[SCHEDULE] now=\$(date '+%F %T %Z') resume_at=${TARGET_FMT} sleep_sec=${SLEEP_SEC}" | tee -a "${RESUME_LOG}"
sleep ${SLEEP_SEC}
echo "[RESUME ] at=\$(date '+%F %T %Z') root=${ROOT_OUT}" | tee -a "${RESUME_LOG}"
"${RUNNER_SCRIPT}" 2>&1 | tee -a "${MAIN_LOG}" "${RESUME_LOG}"
EOF
chmod +x "$RESUME_SCRIPT"

cat > "$WATCHDOG_SCRIPT" <<EOF
#!/usr/bin/env bash
set -euo pipefail
ROOT_OUT="${ROOT_OUT}"
TARGET_TS=${TARGET_TS}
TARGET_FMT="${TARGET_FMT}"
WAKE_FLAG="${WAKE_FLAG}"
WATCHDOG_LOG="${WATCHDOG_LOG}"
RUNNER_SCRIPT="${RUNNER_SCRIPT}"
SESSION_PREFIX="${SESSION_PREFIX}"
ROOT_SLUG="${ROOT_SLUG}"
INTERVAL_SEC="${WATCHDOG_INTERVAL_SEC}"

while true; do
  NOW_TS=\$(date +%s)
  NOW_STR=\$(date '+%F %T %Z')
  RUN_PIDS=\$(pgrep -f "run_case_longcycle.py .*--root-out \${ROOT_OUT}" || true)
  RUNNING=0
  if [[ -n "\${RUN_PIDS}" ]]; then RUNNING=1; fi

  DONE="?"; TOTAL="?"; LAST="?"; STATUS="?"
  PROG="output/train/\${ROOT_OUT}/progress.json"
  if [[ -f "\${PROG}" ]]; then
    DONE=\$(rg -o '"done"\\s*:\\s*[0-9]+' "\${PROG}" | head -n1 | rg -o '[0-9]+' || echo "?")
    TOTAL=\$(rg -o '"total"\\s*:\\s*[0-9]+' "\${PROG}" | head -n1 | rg -o '[0-9]+' || echo "?")
    LAST=\$(rg -o '"last_case"\\s*:\\s*"[^"]+"' "\${PROG}" | head -n1 | sed -E 's/.*"([^"]+)"/\1/' || echo "?")
    STATUS=\$(rg -o '"status"\\s*:\\s*"[^"]+"' "\${PROG}" | head -n1 | sed -E 's/.*"([^"]+)"/\1/' || echo "?")
  fi

  GPU=\$(nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader | tr '\n' '; ')

  {
    echo "=== \${NOW_STR} ==="
    echo "target=\${TARGET_FMT} running=\${RUNNING} pids=\${RUN_PIDS:-none} progress=\${DONE}/\${TOTAL} last=\${LAST} status=\${STATUS}"
    echo "gpu=\${GPU}"
  } >> "\${WATCHDOG_LOG}"

  if [[ "\${NOW_TS}" -ge "\${TARGET_TS}" ]] && [[ "\${RUNNING}" -eq 0 ]] && [[ ! -f "\${WAKE_FLAG}" ]]; then
    echo "[WAKE] \${NOW_STR} training not running after target; start fallback runner" >> "\${WATCHDOG_LOG}"
    touch "\${WAKE_FLAG}"
    FALLBACK_SESSION="\${SESSION_PREFIX}_wake_\${ROOT_SLUG}_\$(date +%Y%m%d_%H%M%S)"
    tmux new-session -d -s "\${FALLBACK_SESSION}" "\${RUNNER_SCRIPT}"
    echo "[WAKE] launched session=\${FALLBACK_SESSION}" >> "\${WATCHDOG_LOG}"
  fi

  sleep "\${INTERVAL_SEC}"
done
EOF
chmod +x "$WATCHDOG_SCRIPT"

tmux new-session -d -s "$RESUME_SESSION" "$RESUME_SCRIPT"
tmux new-session -d -s "$WATCHDOG_SESSION" "$WATCHDOG_SCRIPT"

echo "SCHEDULED"
echo "resume_at=${TARGET_FMT}"
echo "sleep_sec=${SLEEP_SEC}"
echo "resume_session=${RESUME_SESSION}"
echo "watchdog_session=${WATCHDOG_SESSION}"
echo "runner_script=${RUNNER_SCRIPT}"
echo "resume_script=${RESUME_SCRIPT}"
echo "watchdog_script=${WATCHDOG_SCRIPT}"
echo "main_log=${MAIN_LOG}"
echo "resume_log=${RESUME_LOG}"
echo "watchdog_log=${WATCHDOG_LOG}"
