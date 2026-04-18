#!/usr/bin/env bash
# Demo driver — runs the actual Meridian Tax & Advisory persona.
# Meridian is fictitious, so the researcher will return thin evidence.
# The critic will force discovery_needed flags on most questions — this
# is the fallback/self-report mode narrative. Use demo-meridian.sh for
# the clean Anthropic demo against real public data.

set -u

SERVER="http://127.0.0.1:8787"

# Color codes
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; B='\033[0;34m'
M='\033[0;35m'; C='\033[0;36m'; W='\033[1;37m'; X='\033[0m'; BOLD='\033[1m'

# --- Preflight: health check ------------------------------------------------
printf "%b" "${W}[preflight]${X} checking ${SERVER}/health ... "
if ! curl -s -o /dev/null -m 3 -w "%{http_code}" "${SERVER}/health" | grep -q "200"; then
    printf "%b\n" "${R}down${X}"
    printf "%b\n" "${Y}Start the server first: ./start.sh${X}"
    exit 1
fi
printf "%b\n" "${G}ok${X}"

# --- Fire the audit stream --------------------------------------------------
printf "%b\n" "${BOLD}${W}== Openclaw AI Audit — Meridian persona (self-report fallback) ==${X}"
printf "%b\n" "${W}POST ${SERVER}/api/audit-stream${X}"
printf "%b\n" "${Y}Note: Meridian is fictitious — expect thin evidence + many discovery_needed flags.${X}"
echo

PAYLOAD='{"companyUrl":"https://meridiantax.example.com","companyName":"Meridian Tax & Advisory","industry":"accounting","size":"10-50","role":"COO / Operations lead","priority_function":"client document intake and tax preparation"}'

curl -N -s -X POST "${SERVER}/api/audit-stream" \
    -H "Content-Type: application/json" \
    -d "${PAYLOAD}" \
  | awk -v G="$G" -v Y="$Y" -v B="$B" -v M="$M" -v C="$C" -v W="$W" -v R="$R" -v BOLD="$BOLD" -v X="$X" '
    /"type":"pipeline\.start"/        { print BOLD W ">> pipeline.start       " X $0; next }
    /"type":"pipeline\.phase"/        { print BOLD C ">> pipeline.phase       " X $0; next }
    /"type":"pipeline\.complete"/     { print BOLD G ">> pipeline.complete    " X $0; next }
    /"type":"pipeline\.error"/        { print BOLD R "!! pipeline.error       " X $0; next }
    /"type":"agent\.start"/           { print Y    "   agent.start           " X $0; next }
    /"type":"agent\.done"/            { print G    "   agent.done            " X $0; next }
    /"type":"agent\.tool_use"/        { print C    "   agent.tool_use        " X $0; next }
    /"type":"agent\.error"/           { print R    "   agent.error           " X $0; next }
    /"type":"specialist\.result"/     { print BOLD B "   specialist.result     " X $0; next }
    /"type":"critic\.challenge"/      { print M    "   critic.challenge      " X $0; next }
    /"type":"critic\.result"/         { print BOLD M "   critic.result         " X $0; next }
    /"type":"scorecard"/              { print BOLD G ">> scorecard            " X $0; next }
    /"type":"value_chain"/            { print BOLD C ">> value_chain (Porter) " X $0; next }
    /"type":"narrative"/              { print BOLD W ">> narrative            " X $0; next }
    /"type":"evidence"/               { print W    "   evidence dossier      " X substr($0,1,200) "..."; next }
                                      { print      "   " $0 }
  '

echo
printf "%b\n" "${BOLD}${G}== demo complete ==${X}"
