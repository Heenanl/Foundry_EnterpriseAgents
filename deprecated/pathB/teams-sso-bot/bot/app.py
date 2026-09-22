# Copyright (c) Microsoft. All rights reserved.
"""aiohttp host for the Teams SSO bridge bot."""

import sys
import traceback

from aiohttp import web
from aiohttp.web import Request, Response
from botbuilder.core import ConversationState, MemoryStorage, TurnContext, UserState
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.integration.aiohttp import CloudAdapter, ConfigurationBotFrameworkAuthentication
from botbuilder.schema import Activity

from agent_client import AgentClient
from bot import TeamsSsoBot
from config import Config


# botbuilder's ConfigurationBotFrameworkAuthentication reads these attribute names off the settings
# object (MicrosoftAppId / MicrosoftAppPassword / MicrosoftAppType / MicrosoftAppTenantId).
class _AdapterSettings:
    APP_ID = Config.APP_ID
    APP_PASSWORD = Config.APP_PASSWORD
    APP_TYPE = Config.APP_TYPE
    APP_TENANTID = Config.APP_TENANT_ID


ADAPTER = CloudAdapter(ConfigurationBotFrameworkAuthentication(_AdapterSettings()))


async def _on_error(context: TurnContext, error: Exception) -> None:
    print(f"\n [on_turn_error] unhandled error: {error}", file=sys.stderr)
    traceback.print_exc()
    await context.send_activity("The bot hit an error. Please try again.")


ADAPTER.on_turn_error = _on_error

# Single-instance dev storage. MemoryStorage loses OAuth sign-in and agent-selection state on
# restart, and across multiple replicas the token-exchange turn can land on a different instance
# (intermittent sign-in failures). For a scaled/production bot, use durable shared Bot Framework
# storage (e.g. Azure Blob) or pin the app to a single replica.
_storage = MemoryStorage()
_conversation_state = ConversationState(_storage)
_user_state = UserState(_storage)
_agent = AgentClient()
BOT = TeamsSsoBot(_conversation_state, _user_state, _agent)


async def messages(req: Request) -> Response:
    if "application/json" not in req.headers.get("Content-Type", ""):
        return Response(status=415)
    body = await req.json()
    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")
    response = await ADAPTER.process_activity(auth_header, activity, BOT.on_turn)
    if response:
        return web.json_response(data=response.body, status=response.status)
    return Response(status=201)


async def health(_req: Request) -> Response:
    return web.json_response({"status": "ok"})


def create_app() -> web.Application:
    app = web.Application(middlewares=[aiohttp_error_middleware])
    app.router.add_post("/api/messages", messages)
    app.router.add_get("/health", health)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=Config.PORT)  # noqa: S104 - container binds all
