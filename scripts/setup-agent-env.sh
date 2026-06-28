#!/usr/bin/env bash
# One-shot environment setup for AI agents and developers working on this repo.
# - Ensures ~/.local/bin is on PATH (Beads installer and pip --user place binaries here).
# - Installs Beads (bd) from https://github.com/gastownhall/beads when missing.
# - Optionally appends a PATH line to shell rc files (idempotent marker).
# - Skips `bd init` when .beads/metadata.json already exists (avoids clobbering tracked state).
# - Installs backend/requirements.txt with python3 -m pip.
#
# Usage: ./scripts/setup-agent-env.sh
#        ./scripts/setup-agent-env.sh --append-path   # add ~/.local/bin to ~/.bashrc / ~/.profile if missing
#        ./scripts/setup-agent-env.sh --dev           # also install backend/requirements-dev.txt
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="${HOME}/.local/bin:${PATH}"

APPEND_PATH=0
INSTALL_DEV=0
for arg in "$@"; do
  case "$arg" in
    --append-path) APPEND_PATH=1 ;;
    --dev) INSTALL_DEV=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

install_bd() {
  if command -v bd >/dev/null 2>&1; then
    echo "bd already on PATH ($(command -v bd))"
    return 0
  fi
  echo "Installing Beads (bd) from gastownhall/beads (official install.sh)..."
  curl -fsSL https://raw.githubusercontent.com/gastownhall/beads/main/scripts/install.sh | bash
}

append_path_to_shell_rc() {
  local marker='edge-backup-system: ~/.local/bin for Beads and pip user installs'
  for rc in "${HOME}/.bashrc" "${HOME}/.profile"; do
    if [[ ! -f "$rc" ]]; then
      continue
    fi
    if grep -qF "$marker" "$rc" 2>/dev/null; then
      echo "PATH marker already present in $rc"
      continue
    fi
    printf '\n# %s\nexport PATH="${HOME}/.local/bin:${PATH}"\n' "$marker" >>"$rc"
    echo "Appended PATH block to $rc"
  done
}

chmod_beads_dir() {
  if [[ -d "$REPO_ROOT/.beads" ]]; then
    chmod 700 "$REPO_ROOT/.beads" 2>/dev/null || true
  fi
}

cd "$REPO_ROOT"

install_bd
command -v bd >/dev/null 2>&1 || {
  echo "error: bd not found after install; ensure ${HOME}/.local/bin is on PATH" >&2
  exit 1
}
bd version || true
chmod_beads_dir

if [[ ! -f "$REPO_ROOT/.beads/metadata.json" ]]; then
  echo "Initializing Beads (first clone / no metadata)..."
  bd init --quiet
else
  echo "Beads already initialized (.beads/metadata.json present); skipping bd init."
  echo "If the local database and git-tracked .beads/issues.jsonl diverge, restore from git or see Beads docs (import/bootstrap)."
fi

echo "Installing backend Python dependencies..."
python3 -m pip install -r "$REPO_ROOT/backend/requirements.txt"
if [[ "$INSTALL_DEV" -eq 1 ]]; then
  if [[ -f "$REPO_ROOT/backend/requirements-dev.txt" ]]; then
    python3 -m pip install -r "$REPO_ROOT/backend/requirements-dev.txt"
  fi
fi

if [[ "$APPEND_PATH" -eq 1 ]]; then
  append_path_to_shell_rc
fi

echo ""
echo "Done. In new shells, ensure PATH includes ~/.local/bin (or re-login after --append-path)."
echo "Next: cd $REPO_ROOT && bd ready"
