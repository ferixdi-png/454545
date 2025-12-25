#!/bin/bash
# Load secrets from Codespaces shared env into current environment
# This makes GitHub Codespaces secrets available in the shell

SECRETS_FILE="/workspaces/.codespaces/shared/.env"

if [ -f "$SECRETS_FILE" ]; then
    echo "✅ Loading secrets from Codespaces..."
    export $(cat "$SECRETS_FILE" | grep -E "KIE_API_KEY|DATABASE_URL|TELEGRAM_BOT_TOKEN|ADMIN_ID|DB_MAXCONN|FX_RUB_PER_USD" | xargs)
    echo "✅ Secrets loaded successfully"
else
    echo "⚠️  Codespaces secrets file not found at $SECRETS_FILE"
    echo "   Make sure secrets are configured in GitHub repository settings"
fi
