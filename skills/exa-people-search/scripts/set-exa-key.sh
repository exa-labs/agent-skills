#!/bin/sh
# Store an Exa API key for the people-search skill — safely, with no editing.
#
# Run this in YOUR OWN terminal (not through the AI):
#   sh set-exa-key.sh
#
# It prompts once for your key (hidden as you paste), writes it to a private
# credentials file (~/.config/exa/key, mode 600), and verifies it against the
# Exa API. The key never appears on screen, never enters your shell history,
# and never passes through the AI assistant.
#
# The skill reads the key from $EXA_API_KEY first, then from this file — so you
# do NOT need to edit any shell profile (.zshrc/.zshenv/etc.) and you do NOT
# need to restart your terminal.
#
# Works with sh / bash / zsh on macOS and Linux. On Windows, use set-exa-key.ps1.

set -eu

KEYFILE="${EXA_KEY_FILE:-$HOME/.config/exa/key}"

printf '%s\n' "Paste your Exa API key at the prompt, then press Enter."
printf '%s\n' "(You will NOT see anything as you paste — that is intentional.)"
printf '%s' "Exa API key: "

# Hide input in a portable way (works even where 'read -s' is unavailable, e.g. dash).
stty -echo 2>/dev/null || true
IFS= read -r RAWKEY || true
stty echo 2>/dev/null || true
printf '\n'

# Strip ALL whitespace/newlines/CRs (API keys never contain spaces; paste often adds a trailing newline).
KEY=$(printf '%s' "$RAWKEY" | tr -d '[:space:]')

if [ -z "$KEY" ]; then
  printf '%s\n' "No key entered. Nothing was saved. Run the command again."
  exit 1
fi

# Double-paste guard: catches the common "pasted the key twice" mistake, where the
# value is an exact doubling of the real key (e.g. a 36-char key became 72 chars).
LEN=${#KEY}
if [ "$LEN" -gt 8 ] && [ $((LEN % 2)) -eq 0 ]; then
  HALF=$((LEN / 2))
  FIRST=$(printf '%s' "$KEY" | cut -c1-"$HALF")
  SECOND=$(printf '%s' "$KEY" | cut -c$((HALF + 1))-)
  if [ "$FIRST" = "$SECOND" ]; then
    printf '%s\n' "That looks like the key was pasted twice (its length is exactly doubled)."
    printf '%s\n' "Nothing was saved. Run the command again and paste it just once."
    exit 1
  fi
fi

# Write to the private credentials file. Whole-file write (not append) is idempotent:
# re-running cleanly replaces any earlier/broken value instead of stacking lines.
umask 077
mkdir -p "$(dirname "$KEYFILE")"
printf '%s' "$KEY" > "$KEYFILE"
chmod 600 "$KEYFILE" 2>/dev/null || true
printf '%s\n' "Saved to $KEYFILE"

# Best-effort live verification — never prints the key value, only the HTTP status.
if command -v curl >/dev/null 2>&1; then
  printf '%s' "Verifying against the Exa API... "
  CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST https://api.exa.ai/agent/runs \
    -H "x-api-key: $KEY" -H 'Content-Type: application/json' \
    -d '{"query":"hi","effort":"low"}' 2>/dev/null || printf '000')
  case "$CODE" in
    200) printf '%s\n' "OK (HTTP 200). Key saved and verified — you are all set." ;;
    401|403) printf '%s\n' "HTTP $CODE — the key was saved but the API rejected it. Double-check you copied the whole key (and that it has Agent API access), then run this again." ;;
    000) printf '%s\n' "couldn't reach the API (no network or curl blocked). Key was saved; it will be used next time you run the skill." ;;
    *)   printf '%s\n' "HTTP $CODE — key saved, but verification was inconclusive. You can still try running the skill." ;;
  esac
else
  printf '%s\n' "curl not found, so skipping live verification. Key was saved."
fi
