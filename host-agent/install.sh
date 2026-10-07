#!/bin/bash
# Instala el worker del asistente de entrenamiento en /opt/training-agent y deja la unidad systemd lista (no la arranca; lo hace deploy.sh).
#   sudo -E ./install.sh
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Ejecuta con sudo: sudo -E $0" >&2; exit 1; }
SRC="$(cd "$(dirname "$0")" && pwd)"
DST=/opt/training-agent
ETC=/etc/training-agent
RUNAS=claude
RUNHOME="$(getent passwd "$RUNAS" | cut -d: -f6)"
[ -x "$RUNHOME/.local/bin/claude" ] || { echo "No encuentro $RUNHOME/.local/bin/claude" >&2; exit 1; }

kc() {  # kubectl como quien invoca sudo, luego como claude, luego con el kubeconfig de k3s (root)
  local u h out
  for u in "${SUDO_USER:-}" "$RUNAS"; do
    [ -n "$u" ] || continue
    h="$(getent passwd "$u" | cut -d: -f6)"
    out="$(cd "$h" 2>/dev/null && runuser -u "$u" -- env -u KUBECONFIG HOME="$h" kubectl "$@" 2>/dev/null)" && [ -n "$out" ] && { printf '%s' "$out"; return 0; }
  done
  KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl "$@" 2>/dev/null || true
}

# Codigo de solo lectura para el servicio (root); solo logs/work/run son escribibles por claude.
install -d -m 0755 "$DST" "$DST/prompt"
install -m 0644 "$SRC/worker.py" "$SRC/training_mcp.py" "$DST/"
install -m 0644 "$SRC/prompt/system_prompt.md" "$SRC/prompt/eval_prompt.md" "$DST/prompt/"
install -d -m 0750 -o "$RUNAS" -g "$RUNAS" "$DST/logs" "$DST/work" "$DST/run"
install -d -m 0750 -o root -g "$RUNAS" "$ETC"
if [ ! -f "$ETC/env" ] || grep -q CLUSTER_IP "$ETC/env"; then
  CIP="$(kc -n training get svc training -o jsonpath='{.spec.clusterIP}')"
  if [ -z "$CIP" ]; then echo "AVISO: no se pudo leer el Service training/training; edita $ETC/env y pon TRAINING_URL." >&2; URL="http://CLUSTER_IP:8080"; else URL="http://$CIP:8080"; fi
  cat > "$ETC/env" <<ENV
TRAINING_URL=$URL
# TRAINING_MODEL=sonnet
# TRAINING_EFFORT=medium
# TRAINING_TURN_TIMEOUT=600
# TRAINING_EVAL_TIMEOUT=900
# TRAINING_MAX_BUDGET_USD=3
# TRAINING_DEBUG=1
ENV
  chown root:"$RUNAS" "$ETC/env"; chmod 0640 "$ETC/env"
  echo "Creado $ETC/env con TRAINING_URL=$URL"
else
  echo "Conservado $ETC/env existente"
fi

cat > /etc/systemd/system/training-agent.service <<UNIT
[Unit]
Description=Training agent (asistente de entrenamiento y ajuste de rutinas -> claude -p restringido)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUNAS
Group=$RUNAS
Environment=HOME=$RUNHOME
EnvironmentFile=$ETC/env
WorkingDirectory=$DST/work
ExecStart=/usr/bin/python3 $DST/worker.py
Restart=always
RestartSec=5
UMask=0077
NoNewPrivileges=yes
CapabilityBoundingSet=
ProtectSystem=strict
ReadWritePaths=$DST/logs $DST/work $DST/run
ReadWritePaths=-$RUNHOME/.claude -$RUNHOME/.claude.json -$RUNHOME/.cache -$RUNHOME/.local/share -$RUNHOME/.local/state
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
ProtectClock=yes
RestrictSUIDSGID=yes
RestrictRealtime=yes
RestrictNamespaces=yes
LockPersonality=yes
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
SystemCallArchitectures=native

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
[ -s "$ETC/token" ] || echo "AVISO: falta el token. Ejecuta ./set-token.sh."
echo "Instalado en $DST."
