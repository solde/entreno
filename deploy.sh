#!/bin/bash
# Despliega TODO el sistema de Entrenamiento de una vez (idempotente: se puede relanzar).
#   sudo -E /home/claude/homelab-training/deploy.sh [vNN]
#
#   vNN   tag de la imagen (por defecto v1; sube el numero si cambias el codigo)
#
# Orden: ejercicios con imagenes (se descargan una vez) -> namespace + pull secret -> token app<->worker -> clave de sesion
# -> imagen -> manifests (app, acceso de Traefik privado) -> worker del host (claude -p) -> release del portal v19 (menus Entrenamiento y Nutricion).
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Ejecuta con sudo: sudo -E $0" >&2; exit 1; }

TAG="${1:-v1}"
[[ "$TAG" =~ ^v[0-9]+$ ]] || { echo "tag no valido: $TAG" >&2; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"
INFRA="${INFRA:-/home/claude/homelab-infra}"
REG=192.168.1.224:30300/dsoldevila/homelab-training
OWNER="$(stat -c %U "$INFRA")"
RUN_AS="${SUDO_USER:-$OWNER}"
PORTAL_TAG="${PORTAL_TAG:-v20}"

# kubectl como quien invoca sudo; si su kubeconfig no sirve, el de k3s (root)
if sudo -u "$RUN_AS" -E kubectl get ns >/dev/null 2>&1; then
  KC_USER="$RUN_AS"
else
  export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
  KC_USER=root
  kubectl get ns >/dev/null 2>&1 || { echo "kubectl no funciona ni como $RUN_AS ni como root" >&2; exit 1; }
fi
as_kc() { if [ "$KC_USER" = root ]; then "$@"; else sudo -u "$KC_USER" -E "$@"; fi; }
k() { as_kc kubectl "$@"; }
step() { printf '\n==> %s\n' "$*"; }

[ -S /run/buildkit/buildkitd.sock ] || { echo "buildkitd no esta activo (systemctl start buildkitd)" >&2; exit 1; }
[ -d "${DOCKER_CONFIG_REGISTRY:-/root/.docker}" ] || { echo "faltan las credenciales del registry en /root/.docker" >&2; exit 1; }

step "1/8 Base de ejercicios con imagenes (free-exercise-db, dominio publico)"
if [ -d "$HERE/static/ex" ] && [ "$(ls "$HERE/static/ex" | wc -l)" -gt 800 ] && [ -s "$HERE/data/exercises.json" ]; then
  echo "ya descargada ($(ls "$HERE/static/ex" | wc -l) ejercicios con imagen)"
else
  VENV="$(mktemp -d)"; trap 'rm -rf "$VENV"' EXIT
  python3 -m venv "$VENV" && "$VENV/bin/pip" install --quiet Pillow
  "$VENV/bin/python" "$HERE/tools/build_exercises.py"
  chown -R "$OWNER" "$HERE/static/ex" "$HERE/data"
  rm -rf "$VENV"; trap - EXIT
fi

step "2/8 Namespace training y pull secret del registry"
k apply -f "$INFRA/namespaces/namespaces.yaml" >/dev/null
if ! k -n training get secret gitea-registry >/dev/null 2>&1; then
  k -n finance get secret gitea-registry -o json \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); m=d["metadata"]; d["metadata"]={"name":m["name"],"namespace":"training"}; print(json.dumps(d))' \
    | k apply -f - >/dev/null
  echo "gitea-registry copiado desde finance"
fi

step "3/8 Token compartido app <-> worker"
if [ -s /etc/training-agent/token ] && k -n training get secret training-agent-token >/dev/null 2>&1; then
  echo "ya existe, se conserva"
else
  as_kc "$HERE/host-agent/set-token.sh" --force
fi

step "4/8 Clave de sesion (propia del sitio publico; la crea homelab-infra/public-apps/deploy.sh)"
k -n training get secret training-auth >/dev/null 2>&1 || { echo "falta training-auth: ejecuta antes sudo -E $INFRA/public-apps/deploy.sh" >&2; exit 1; }

step "5/8 Imagen homelab-training:$TAG"
DOCKER_CONFIG="${DOCKER_CONFIG_REGISTRY:-/root/.docker}" buildctl --addr unix:///run/buildkit/buildkitd.sock build --frontend dockerfile.v0 \
  --local context="$HERE" --local dockerfile="$HERE" \
  --output "type=image,name=$REG:$TAG,push=true,registry.insecure=true"
sed -i -E "s#(homelab-training:)v[0-9]+#\1$TAG#" "$INFRA/training/deployment.yaml"
chown "$OWNER" "$INFRA/training/deployment.yaml"

step "6/8 Manifests (app; se publica en entreno.solde.cat y nutricion.solde.cat con public-apps/deploy.sh)"
k apply -f "$INFRA/training/deployment.yaml" -f "$INFRA/training/network-policies.yaml"
k -n training rollout restart deploy/training >/dev/null
k -n training rollout status deploy/training --timeout=240s

step "7/8 Worker del host (Claude: chat y ajuste de rutinas)"
"$HERE/host-agent/install.sh"
systemctl enable training-agent >/dev/null 2>&1
systemctl restart training-agent
sleep 2
systemctl is-active training-agent

echo
echo "LISTO (imagen $TAG). Entreno y Nutricion estan en https://entreno.solde.cat y https://nutricion.solde.cat (ya no bajo portal.solde.cat)."
echo "Luego commitea el cambio de tag en $INFRA (training/deployment.yaml)."
