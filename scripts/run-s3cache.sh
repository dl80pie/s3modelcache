#!/usr/bin/env bash
set -euo pipefail

# run-s3cache.sh
# Lokales Ausführen des S3ModelCache: lädt ein HuggingFace-Modell in den lokalen Cache
# und lädt es (komprimiert oder als Verzeichnis) in ein S3-kompatibles Bucket hoch.
#
# Voraussetzungen:
# - Python 3.10+
# - Zugriffsdaten für S3 als Umgebungsvariablen
# - Optional: .env im Repo-Root (wird automatisch geladen)
# - Optional: Proxy/CA-Variablen (HTTP_PROXY, HTTPS_PROXY, NO_PROXY, REQUESTS_CA_BUNDLE, ...)
# - Optional: HUGGINGFACE_HUB_TOKEN für private Modelle
#
# Nutzung:
#   scripts/run-s3cache.sh [MODEL_ID]
#
# Benötigte Variablen (oder via .env):
#   MODEL_ID (kann auch als 1. Argument übergeben werden)
#   S3_BUCKET, S3_ENDPOINT, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY
#   Optional: S3_REGION (default: us-east-1), S3_PREFIX (default: models/), S3_VERIFY_SSL (true/false), S3_ROOT_CA_PATH
#
# Beispiel .env:
#   MODEL_ID=microsoft/Phi-3-mini-4k-instruct
#   S3_BUCKET=models
#   S3_ENDPOINT=https://minio.minio.svc.cluster.local
#   S3_REGION=us-east-1
#   S3_PREFIX=models/v1/
#   S3_VERIFY_SSL=true
#   S3_ACCESS_KEY_ID=xxx
#   S3_SECRET_ACCESS_KEY=yyy
#   HUGGINGFACE_HUB_TOKEN=hf_xxx
#   HTTP_PROXY=http://proxy.local:3128
#   HTTPS_PROXY=http://proxy.local:3128
#   NO_PROXY=localhost,127.0.0.1,.svc,.cluster.local,minio.minio.svc.cluster.local

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# .env laden, falls vorhanden
if [[ -f .env ]]; then
  echo "[info] Lade .env ..."
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# MODEL_ID aus 1. Argument, falls gesetzt
if [[ "${1:-}" != "" ]]; then
  export MODEL_ID="${1}"
fi

# Defaults setzen
export S3_REGION="${S3_REGION:-us-east-1}"
export S3_PREFIX="${S3_PREFIX:-models/}"
export S3_VERIFY_SSL="${S3_VERIFY_SSL:-true}"
export S3_BUCKET="${S3_BUCKET:-${HCP_NAMESPACE:-}}"
export S3_ENDPOINT="${S3_ENDPOINT:-${HCP_ENDPOINT:-}}"
export S3_ACCESS_KEY_ID="${S3_ACCESS_KEY_ID:-${HCP_ACCESS_KEY:-}}"
export S3_SECRET_ACCESS_KEY="${S3_SECRET_ACCESS_KEY:-${HCP_SECRET_KEY:-}}"
export S3_REGION="${S3_REGION:-${HCP_REGION:-us-east-1}}"
export S3_PREFIX="${S3_PREFIX:-${HCP_PREFIX:-models/}}"
export S3_VERIFY_SSL="${S3_VERIFY_SSL:-${HCP_VERIFY_SSL:-true}}"
if [[ -n "${HCP_ROOT_CA_PATH:-}" && -z "${S3_ROOT_CA_PATH:-}" ]]; then
  export S3_ROOT_CA_PATH="${HCP_ROOT_CA_PATH}"
fi
if [[ -n "${HCP_STORE_AS_ARCHIVE:-}" && -z "${S3_STORE_AS_ARCHIVE:-}" ]]; then
  export S3_STORE_AS_ARCHIVE="${HCP_STORE_AS_ARCHIVE}"
fi

# Pflichtvariablen prüfen
missing=()
for v in MODEL_ID S3_BUCKET S3_ENDPOINT S3_ACCESS_KEY_ID S3_SECRET_ACCESS_KEY; do
  if [[ -z "${!v:-}" ]]; then
    missing+=("$v")
  fi
done
if (( ${#missing[@]} > 0 )); then
  echo "[error] Fehlende Variablen: ${missing[*]}" >&2
  echo "        Setze sie in der Umgebung oder .env, oder übergebe MODEL_ID als Argument." >&2
  exit 1
fi

# Python-Umgebung vorbereiten (.venv)
if [[ ! -d .venv ]]; then
  echo "[info] Erstelle Python-venv ..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# Abhängigkeiten installieren
if command -v uv >/dev/null 2>&1; then
  echo "[info] Installiere Dependencies mit uv ..."
  uv pip install --upgrade pip wheel setuptools
  uv pip install -r requirements.txt
else
  echo "[info] Installiere Dependencies mit pip ..."
  pip install --upgrade pip wheel setuptools
  pip install -r requirements.txt
fi

# Diagnoseausgabe (ohne Secrets)
echo "[info] MODEL_ID=${MODEL_ID}"
echo "[info] S3_BUCKET=${S3_BUCKET}"
echo "[info] S3_ENDPOINT=${S3_ENDPOINT}"
echo "[info] S3_REGION=${S3_REGION}"
echo "[info] S3_PREFIX=${S3_PREFIX}"
echo "[info] S3_VERIFY_SSL=${S3_VERIFY_SSL}"
if [[ -n "${S3_ROOT_CA_PATH:-}" ]]; then
  echo "[info] S3_ROOT_CA_PATH=${S3_ROOT_CA_PATH}"
fi
# Map Root-CA to common TLS envs for requests/boto3 if not already set
if [[ -n "${S3_ROOT_CA_PATH:-}" ]]; then
  export REQUESTS_CA_BUNDLE="${REQUESTS_CA_BUNDLE:-${S3_ROOT_CA_PATH}}"
  export AWS_CA_BUNDLE="${AWS_CA_BUNDLE:-${S3_ROOT_CA_PATH}}"
fi
if [[ -n "${HTTP_PROXY:-}${http_proxy:-}" || -n "${HTTPS_PROXY:-}${https_proxy:-}" ]]; then
  echo "[info] Proxy erkannt (HTTP_PROXY/HTTPS_PROXY)"
fi
if [[ -n "${NO_PROXY:-}${no_proxy:-}" ]]; then
  echo "[info] NO_PROXY gesetzt"
fi
if [[ -n "${HUGGINGFACE_HUB_TOKEN:-}" ]]; then
  echo "[info] HUGGINGFACE_HUB_TOKEN ist gesetzt"
fi

# Ausführen
echo "[info] Starte Caching-Prozess ..."
python3 cache_model.py
status=$?
if [[ $status -ne 0 ]]; then
  echo "[error] Caching fehlgeschlagen (exit ${status})" >&2
  exit $status
fi

echo "[ok] Caching erfolgreich abgeschlossen"
