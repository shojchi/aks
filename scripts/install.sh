#!/usr/bin/env bash
# AKS one-time setup: registers the `aks` command in your shell.

set -euo pipefail

AKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BINARY="$AKS_DIR/.venv/bin/aks"
ZSHRC="$HOME/.zshrc"

echo ""
echo "AKS Setup"
echo "---------"

# --- Guard: venv must exist -----------------------------------------------
if [[ ! -f "$BINARY" ]]; then
  echo "Error: venv not found at $BINARY"
  echo "Run 'uv sync' or 'pip install -e .' inside $AKS_DIR first."
  exit 1
fi

# --- Check if already configured ------------------------------------------
if grep -qF 'alias aks=' "$ZSHRC" 2>/dev/null; then
  echo "Already configured — 'aks' alias found in $ZSHRC"
  echo "Run 'source ~/.zshrc' (or open a new terminal) if the command isn't working."
  exit 0
fi

# --- Ask permission -------------------------------------------------------
echo "This will add two lines to $ZSHRC:"
echo ""
echo "  export AKS_HOME=\"$AKS_DIR\""
echo "  alias aks=\"$BINARY\""
echo ""
read -r -p "Add to ~/.zshrc? [y/N] " answer

case "$answer" in
  [yY][eE][sS]|[yY])
    {
      echo ""
      echo "# AKS — Agent Knowledge System"
      echo "export AKS_HOME=\"$AKS_DIR\""
      echo "alias aks=\"$BINARY\""
    } >> "$ZSHRC"
    echo ""
    echo "Done. Run 'source ~/.zshrc' to activate in this session,"
    echo "or open a new terminal — it will work automatically from then on."
    ;;
  *)
    echo "Skipped. You can run this script again any time."
    ;;
esac
