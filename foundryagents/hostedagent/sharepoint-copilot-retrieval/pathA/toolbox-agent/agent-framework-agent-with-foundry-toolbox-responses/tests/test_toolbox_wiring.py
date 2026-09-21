"""Offline regression checks for the SharePoint Foundry Toolbox agent."""

import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if os.name == "nt" and not str(ROOT).startswith("\\\\?\\"):
    ROOT = Path("\\\\?\\" + str(ROOT))
SOURCE = ROOT / "src/agent-framework-agent-sharepoint-copilot-retrieval/main.py"
spec = importlib.util.spec_from_file_location("sharepoint_toolbox_agent", SOURCE)
assert spec is not None and spec.loader is not None
agent_module = importlib.util.module_from_spec(spec)
with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}):
    spec.loader.exec_module(agent_module)


class ToolboxWiringTests(unittest.TestCase):
    def environment(self, toolbox_name="sharepoint-retrieval-tools"):
        return {
            "FOUNDRY_PROJECT_ENDPOINT": "https://example.services.ai.azure.com/api/projects/test/",
            "TOOLBOX_NAME": toolbox_name,
            "AZURE_AI_MODEL_DEPLOYMENT_NAME": "test-model",
            # Stale endpoint/disable settings must not bypass the configured toolbox.
            "TOOLBOX_ENDPOINT": "https://wrong.example/mcp",
            "ENABLE_TOOLBOX": "false",
        }

    def test_registers_remote_toolbox_not_local_obo(self):
        for toolbox_name in ("sharepoint-retrieval-tools", "another-retrieval-toolbox"):
            with self.subTest(toolbox_name=toolbox_name):
                credential = object()
                with (
                    patch.dict(os.environ, self.environment(toolbox_name), clear=True),
                    patch.object(agent_module, "FoundryToolbox") as toolbox,
                    patch.object(agent_module, "FoundryChatClient") as client,
                    patch.object(agent_module, "Agent") as agent,
                ):
                    result = agent_module.create_agent(credential)
                toolbox.assert_called_once_with(
                    credential,
                    url="https://example.services.ai.azure.com/api/projects/test/"
                    f"toolboxes/{toolbox_name}/mcp?api-version=v1",
                )
                client.assert_called_once_with(
                    project_endpoint="https://example.services.ai.azure.com/api/projects/test",
                    model="test-model",
                    credential=credential,
                )
                options = agent.call_args.kwargs
                self.assertIs(options["tools"], toolbox.return_value)
                self.assertIs(options["client"], client.return_value)
                self.assertEqual(options["default_options"], {"store": False})
                self.assertIn("that turn's returned results", options["instructions"])
                self.assertIn("Never reuse earlier document content", options["instructions"])
                self.assertIs(result, agent.return_value)
        for name in (
            "sharepoint_retrieve", "_current_user_assertion", "_get_obo_app",
            "CLIENT_USER_TOKEN_HEADER", "_ResilientResponsesHostServer",
        ):
            self.assertFalse(hasattr(agent_module, name), name)

    def test_missing_toolbox_config_fails_instead_of_local_fallback(self):
        with patch.dict(os.environ, {"FOUNDRY_PROJECT_ENDPOINT": "https://example.test"}, clear=True):
            with self.assertRaisesRegex(KeyError, "TOOLBOX_NAME"):
                agent_module.create_agent(object())

    def test_toolbox_failure_is_not_silently_disabled(self):
        with (
            patch.dict(os.environ, self.environment(), clear=True),
            patch.object(agent_module, "FoundryToolbox", side_effect=RuntimeError("toolbox unavailable")),
            patch.object(agent_module, "Agent") as agent,
        ):
            with self.assertRaisesRegex(RuntimeError, "toolbox unavailable"):
                agent_module.create_agent(object())
        agent.assert_not_called()

    def test_main_enables_resilient_tasks_before_starting_responses_host(self):
        expected_agent = object()
        with (
            patch("azure.ai.agentserver.core.tasks.set_resilient_tasks_enabled") as enable,
            patch.object(agent_module, "DefaultAzureCredential") as credential,
            patch.object(agent_module, "create_agent") as create_agent,
            patch.object(agent_module, "ResponsesHostServer") as server,
        ):
            def construct_agent(value):
                enable.assert_called_once_with(True)
                self.assertIs(value, credential.return_value)
                return expected_agent

            create_agent.side_effect = construct_agent
            agent_module.main()
        create_agent.assert_called_once_with(credential.return_value)
        server.assert_called_once_with(expected_agent)
        server.return_value.run.assert_called_once_with()

    def test_real_sdk_construction_is_lazy_and_offline(self):
        class OfflineCredential:
            def get_token(self, *scopes, **kwargs):
                raise AssertionError("Construction must not request a token")

        with (
            patch.dict(os.environ, self.environment(), clear=True),
            patch("socket.socket.connect", side_effect=AssertionError("Network access is forbidden")),
            patch.object(agent_module, "Agent", wraps=agent_module.Agent) as agent,
        ):
            result = agent_module.create_agent(OfflineCredential())
        self.assertIsNotNone(result)
        self.assertIsInstance(agent.call_args.kwargs["tools"], agent_module.FoundryToolbox)


if __name__ == "__main__":
    unittest.main()