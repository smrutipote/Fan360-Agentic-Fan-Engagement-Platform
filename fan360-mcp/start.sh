#!/bin/bash
# Safely export env vars from .env, handling values with semicolons
export PATH="$PATH:$HOME/.dotnet/tools"
set -a
while IFS='=' read -r key value; do
  # Skip comments and empty lines
  [[ "$key" =~ ^[[:space:]]*# ]] && continue
  [[ -z "$key" ]] && continue
  # Strip surrounding double quotes from value
  value="${value%\"}"
  value="${value#\"}"
  export "$key=$value"
done < .env
set +a

exec dab start "$@"
