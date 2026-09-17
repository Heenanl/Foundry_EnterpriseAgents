# Copyright (c) Microsoft. All rights reserved.
"""Configuration for the Teams SSO bridge bot.

All values come from environment variables so the same image runs locally and in a
Container App / App Service. The bot itself holds NO user secrets — the user's token is
obtained per-turn via Teams silent SSO (Bot Service OAuth connection) and forwarded to the
hosted agent; only the bot's own app password (for the Bot Framework channel) is a secret.
"""

import os


class Config:
    PORT = int(os.getenv("PORT", "3978"))

    # ── Bot Framework identity (the Azure Bot registration) ──────────────────
    APP_ID = os.environ.get("MicrosoftAppId", "")
    APP_PASSWORD = os.environ.get("MicrosoftAppPassword", "")
    APP_TYPE = os.environ.get("MicrosoftAppType", "SingleTenant")
    APP_TENANT_ID = os.environ.get("MicrosoftAppTenantId", "")

    # Name of the Bot Service OAuth Connection Setting that does Teams SSO. Its AAD app must be
    # configured for silent SSO (see scripts/Configure-TeamsSso-App.ps1) and expose access_as_user.
    # The token it returns has audience = that SSO/OBO app — exactly the assertion the hosted agent
    # needs for its On-Behalf-Of exchange to Microsoft Graph.
    OAUTH_CONNECTION_NAME = os.environ.get("OAUTH_CONNECTION_NAME", "teams-sso")

    # ── Downstream hosted agent(s) (the x-client-user-token consumers) ───────
    # Foundry project endpoint, e.g. https://<account>.services.ai.azure.com/api/projects/<project>
    FOUNDRY_PROJECT_ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").rstrip("/")
    # Default hosted-agent name (used as the Responses "model" id) when the user hasn't picked one.
    DEFAULT_AGENT_NAME = os.environ.get("AGENT_NAME", "")
    # Optional allow-list of agent names this ONE bot can route to (comma-separated). Empty = only the
    # default. One bot fronts many agents — no per-agent bot registration needed. Users switch with
    # "/use <name>"; "/agents" lists these.
    ALLOWED_AGENTS = [a.strip() for a in os.environ.get("AGENTS", "").split(",") if a.strip()]
    FOUNDRY_API_VERSION = os.environ.get("FOUNDRY_API_VERSION", "2025-11-15-preview")
    # Scope the bot's OWN managed identity uses to call Foundry (it needs Foundry Agent Consumer).
    FOUNDRY_SCOPE = os.environ.get("FOUNDRY_SCOPE", "https://ai.azure.com/.default")

    @classmethod
    def agent_choices(cls) -> list[str]:
        """All agent names this bot can route to (default first, de-duplicated)."""
        names = [cls.DEFAULT_AGENT_NAME] if cls.DEFAULT_AGENT_NAME else []
        for a in cls.ALLOWED_AGENTS:
            if a not in names:
                names.append(a)
        return names
