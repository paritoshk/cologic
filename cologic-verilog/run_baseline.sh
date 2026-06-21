#!/usr/bin/env bash
# Self-driving HUD-cloud baseline: deploy env -> sync taskset -> hosted eval.
# Everything runs on HUD cloud (no local Docker). Streams to a gitignored logfile.
#
#   ./run_baseline.sh smoke   # 1 task, group 1  — cheap end-to-end check (~cents)
#   ./run_baseline.sh full    # all 3 tracks, group $GROUP — the real baseline
#
# Watch:  tail -f logs/<newest>.log     Results land in results/baseline_<ts>.json
set -uo pipefail
cd "$(dirname "$0")"

MODE="${1:-smoke}"
TASKSET="${TASKSET:-cologic-verilog}"
GROUP="${GROUP:-3}"                    # rollouts per task for the full run
AGENT="${AGENT:-claude}"
TS="$(date +%Y%m%d_%H%M%S)"
mkdir -p logs results
LOG="logs/${MODE}_${TS}.log"
RESULT="results/${MODE}_${TS}.json"

log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

log "=== HUD cloud baseline: mode=$MODE taskset=$TASKSET group=$GROUP agent=$AGENT ==="

# 1) Deploy the env image to HUD cloud (idempotent; layer-cached). ponytail: always
#    deploy — HUD caches, and it's the only way to be sure the cloud image is current.
log "STEP 1/3 deploy env (hud deploy .)"
hud deploy . --yes >>"$LOG" 2>&1 || hud deploy . >>"$LOG" 2>&1
log "deploy exit=$?"

# 2) Register the taskset on the platform.
log "STEP 2/3 sync taskset (hud sync tasks $TASKSET)"
hud sync tasks "$TASKSET" --yes >>"$LOG" 2>&1
log "sync exit=$?"

# 3) Hosted eval — a platform taskset defaults to --remote, so the whole rollout
#    (agent + env) runs in HUD containers. No --json flag exists; --verbose puts the
#    per-task reward/subscores in the log, and the run is also a job on the dashboard.
if [ "$MODE" = "smoke" ]; then
  EVAL_ARGS=(--task-ids stream-arb-fifo-repair --group 1)
else
  EVAL_ARGS=(--full --group "$GROUP")
fi
log "STEP 3/3 hosted eval (hud eval $TASKSET $AGENT --remote ${EVAL_ARGS[*]} --verbose)"
hud eval "$TASKSET" "$AGENT" --remote "${EVAL_ARGS[@]}" -y --verbose >>"$LOG" 2>&1
EV=$?
log "eval exit=$EV"

# Best-effort: scrape the printed reward/pass lines into a results JSON for charting.
grep -iE 'reward|pass|subscore|task_id|slug|stream-arb' "$LOG" > "$RESULT" 2>/dev/null || true
[ -s "$RESULT" ] && log "scraped reward lines -> $RESULT" || log "NOTE: parse $LOG (HUD dashboard has the run)"
log "=== done (mode=$MODE) ==="
exit $EV
