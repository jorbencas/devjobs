#!/bin/bash
# pipeline_ipc.sh — Helper para IPC via filesystem desde bash
# Uso: source pipeline_ipc.sh && ipc_update_status monitor status=compressing file=video.mp4

PIPELINE_DATA="${PIPELINE_DATA:-/data}"
STATUS_FILE="$PIPELINE_DATA/pipeline_status.json"
LOGS_FILE="$PIPELINE_DATA/pipeline_logs.json"

ipc_update_status() {
    local service="$1"
    shift
    local ts
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local json="{\"$service\":{"
    local first=true
    for arg in "$@"; do
        local key="${arg%%=*}"
        local val="${arg#*=}"
        if [[ "$first" == "true" ]]; then
            first=false
        else
            json+=","
        fi
        # Detectar si es número o booleano
        if [[ "$val" =~ ^[0-9]+$ ]] || [[ "$val" == "true" ]] || [[ "$val" == "false" ]]; then
            json+="\"$key\":$val"
        else
            json+="\"$key\":\"$val\""
        fi
    done
    json+=",\"updated_at\":\"$ts\"},\"last_update\":\"$ts\"}"

    mkdir -p "$PIPELINE_DATA"
    # Merge con status existente
    if [[ -f "$STATUS_FILE" ]]; then
        python3 -c "
import json,sys
try:
    d=json.load(open('$STATUS_FILE'))
except: d={}
d['$service']=$(python3 -c "import json;print(json.dumps({a.split('=',1)[0]:a.split('=',1)[1] if not a.split('=',1)[1].replace('.','').isdigit() and a.split('=',1)[1] not in ('true','false') else (True if a.split('=',1)[1]=='true' else False if a.split('=',1)[1]=='false' else (int(a.split('=',1)[1]) if '.' not in a.split('=',1)[1] else float(a.split('=',1)[1]))) for a in '$*' if '=' in a} except: {})" 2>/dev/null)
d['last_update']='$ts'
json.dump(d,open('$STATUS_FILE','w'),indent=2,ensure_ascii=False)
" 2>/dev/null || echo "$json" > "$STATUS_FILE"
    else
        echo "$json" > "$STATUS_FILE"
    fi
}

ipc_remove_status() {
    local service="$1"
    if [[ -f "$STATUS_FILE" ]] && command -v python3 >/dev/null 2>&1; then
        python3 -c "
import json
d=json.load(open('$STATUS_FILE'))
d.pop('$service',None)
json.dump(d,open('$STATUS_FILE','w'),indent=2,ensure_ascii=False)
" 2>/dev/null
    fi
}

ipc_append_log() {
    local source="$1"
    local message="$2"
    local ts
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    mkdir -p "$PIPELINE_DATA"
    python3 -c "
import json
f='$LOGS_FILE'
try: logs=json.load(open(f))
except: logs=[]
logs.append({'ts':'$ts','src':'$source','msg':'$message'})
if len(logs)>200: logs=logs[-200:]
json.dump(logs,open(f,'w'),ensure_ascii=False)
" 2>/dev/null
}
