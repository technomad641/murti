#!/bin/zsh
# Launch the dictation menu-bar app.
# To use the online translate/romanize path, export ANTHROPIC_API_KEY first.
cd "$(dirname "$0")"
exec ./.venv/bin/python -m murti.app
