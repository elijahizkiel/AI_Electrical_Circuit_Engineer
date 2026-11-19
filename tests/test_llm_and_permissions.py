import asyncio
import pytest
from circuit_agent.llm import MockProvider, ProviderRegistry
from circuit_agent.permissions import ToolPermissionError, require_tool_permission

def test_mock_provider_validates_required_output():
 registry=ProviderRegistry(); registry.register("mock",MockProvider({"result":{"answer":"ok"}}))
 output=asyncio.run(registry.generate("mock",system_prompt="x",user_payload={},response_schema={"title":"result","required":["answer"]}))
 assert output.content == {"answer":"ok"}
def test_permission_guard_rejects_unapproved_tool():
 with pytest.raises(ToolPermissionError): require_tool_permission("requirements_analyst","generate_spice_netlist")
