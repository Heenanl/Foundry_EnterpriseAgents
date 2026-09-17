# Copyright (c) Microsoft. All rights reserved.
"""Teams SSO bot: silently sign the user in, then relay to the per-user hosted agent.

Flow per user message:
  1. An ``OAuthPrompt`` bound to the ``teams-sso`` Bot Service OAuth connection triggers Teams
     SILENT SSO (``signin/tokenExchange``). With the SSO app configured correctly
     (scripts/Configure-TeamsSso-App.ps1) no consent card appears.
  2. The prompt yields the user's delegated token (aud = SSO/OBO app, scope access_as_user).
  3. The bot calls the hosted agent with that token as ``x-client-user-token`` (see agent_client.py)
     and returns the answer.

The bot stores no user tokens; Bot Service holds the OAuth token cache.
"""

from botbuilder.core import ConversationState, MessageFactory, TurnContext, UserState
from botbuilder.dialogs import Dialog, DialogSet, DialogTurnStatus, WaterfallDialog, WaterfallStepContext
from botbuilder.dialogs.prompts import OAuthPrompt, OAuthPromptSettings
from botbuilder.core.teams import TeamsActivityHandler

from agent_client import AgentClient
from config import Config

_SSO_DIALOG = "sso-dialog"
_SSO_PROMPT = "sso-prompt"


class TeamsSsoBot(TeamsActivityHandler):
    def __init__(
        self,
        conversation_state: ConversationState,
        user_state: UserState,
        agent: AgentClient,
    ) -> None:
        self._conversation_state = conversation_state
        self._user_state = user_state
        self._agent = agent
        self._dialog_state = conversation_state.create_property("DialogState")
        # One bot fronts many agents: the user's chosen agent is kept in user state (default applies
        # until they switch with "/use <name>"). No per-agent bot registration.
        self._selected_agent = user_state.create_property("SelectedAgent")

        self._dialogs = DialogSet(self._dialog_state)
        self._dialogs.add(
            OAuthPrompt(
                _SSO_PROMPT,
                OAuthPromptSettings(
                    connection_name=Config.OAUTH_CONNECTION_NAME,
                    title="Sign in",
                    text="Signing you in to access your SharePoint content…",
                    timeout=300000,
                ),
            )
        )
        self._dialogs.add(
            WaterfallDialog(_SSO_DIALOG, [self._prompt_step, self._relay_step])
        )

    # ── Activity routing ─────────────────────────────────────────────────────
    async def on_message_activity(self, turn_context: TurnContext) -> None:
        text = (turn_context.activity.text or "").strip()
        # Agent-selection commands need no sign-in; handle them before the SSO dialog.
        if text.startswith("/"):
            await self._handle_command(turn_context, text)
            return
        await self._run_dialog(turn_context)

    async def on_teams_signin_verify_state(self, turn_context: TurnContext) -> None:
        await self._run_dialog(turn_context)

    async def on_teams_signin_token_exchange(self, turn_context: TurnContext) -> None:
        await self._run_dialog(turn_context)

    async def on_turn(self, turn_context: TurnContext) -> None:
        await super().on_turn(turn_context)
        # Persist any state changes the dialog stack made this turn.
        await self._conversation_state.save_changes(turn_context, False)
        await self._user_state.save_changes(turn_context, False)

    # ── Commands: list / switch the target agent ─────────────────────────────
    async def _handle_command(self, turn_context: TurnContext, text: str) -> None:
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        current = await self._current_agent(turn_context)
        choices = Config.agent_choices()

        if cmd in ("/help", "/commands"):
            await turn_context.send_activity(
                MessageFactory.text(
                    "Commands:\n"
                    "- `/agents` — list agents I can answer from\n"
                    "- `/use <name>` — switch the agent\n"
                    "- ask a question — answered from your SharePoint content\n"
                    f"\nCurrent agent: **{current or '(none configured)'}**"
                )
            )
        elif cmd == "/agents":
            listing = "\n".join(f"- {'**' + a + '** (current)' if a == current else a}" for a in choices) or "(none configured)"
            await turn_context.send_activity(MessageFactory.text(f"Agents:\n{listing}"))
        elif cmd == "/use":
            target = parts[1].strip() if len(parts) > 1 else ""
            if target and target in choices:
                await self._selected_agent.set(turn_context, target)
                await turn_context.send_activity(MessageFactory.text(f"Now using **{target}**."))
            else:
                await turn_context.send_activity(
                    MessageFactory.text(f"Unknown agent `{target}`. Try `/agents` to see the list.")
                )
        else:
            await turn_context.send_activity(MessageFactory.text("Unknown command. Try `/help`."))

    async def _current_agent(self, turn_context: TurnContext) -> str:
        return await self._selected_agent.get(turn_context, lambda: Config.DEFAULT_AGENT_NAME)

    # ── Dialog steps ─────────────────────────────────────────────────────────
    async def _run_dialog(self, turn_context: TurnContext) -> None:
        dialog_context = await self._dialogs.create_context(turn_context)
        result = await dialog_context.continue_dialog()
        if result.status == DialogTurnStatus.Empty:
            await dialog_context.begin_dialog(_SSO_DIALOG)

    async def _prompt_step(self, step: WaterfallStepContext):
        return await step.begin_dialog(_SSO_PROMPT)

    async def _relay_step(self, step: WaterfallStepContext):
        token_response = step.result
        if not token_response or not token_response.token:
            await step.context.send_activity(
                MessageFactory.text("Sign-in was not completed, so I can't reach your SharePoint content.")
            )
            return await step.end_dialog()

        user_text = (step.context.activity.text or "").strip()
        # The token-exchange turn has no user text; ask them to resend their question.
        if not user_text:
            await step.context.send_activity(
                MessageFactory.text("You're signed in. Send your question and I'll answer from SharePoint.")
            )
            return await step.end_dialog()

        agent_name = await self._current_agent(step.context)
        if not agent_name:
            await step.context.send_activity(
                MessageFactory.text("No agent is configured. Ask an admin to set AGENT_NAME, or pick one with `/agents`.")
            )
            return await step.end_dialog()

        answer = await self._agent.ask(agent_name, user_text, token_response.token)
        await step.context.send_activity(MessageFactory.text(answer))
        return await step.end_dialog()
