#!/bin/bash
# Genera el token compartido app <-> worker sin imprimirlo: /etc/training-agent/token (0640 root:claude) y Secret training/training-agent-token.
#   ./set-token.sh [--force]      (con sudo y kubectl disponibles)
set -euo pipefail
ETC=/etc/training-agent
if sudo test -s "$ETC/token" && [ "${1:-}" != "--force" ]; then echo "Ya existe $ETC/token. Usa --force para regenerarlo." >&2; exit 0; fi
TOKEN="$(openssl rand -hex 32)"
sudo install -d -m 0750 -o root -g claude "$ETC"
printf '%s' "$TOKEN" | sudo tee "$ETC/token" >/dev/null
sudo chown root:claude "$ETC/token"; sudo chmod 0640 "$ETC/token"
kubectl get ns training >/dev/null 2>&1 || kubectl create ns training >/dev/null
printf '%s' "$TOKEN" | kubectl -n training create secret generic training-agent-token --from-file=token=/dev/stdin --dry-run=client -o yaml | kubectl apply -f - >/dev/null
unset TOKEN
echo "Token guardado en $ETC/token y Secret training/training-agent-token actualizado."
kubectl -n training rollout restart deploy/training >/dev/null 2>&1 && echo "Reiniciado deploy/training." || true
sudo systemctl try-restart training-agent 2>/dev/null || true
