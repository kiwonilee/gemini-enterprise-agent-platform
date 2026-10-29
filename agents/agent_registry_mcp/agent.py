# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from dotenv import load_dotenv

from google.adk.integrations.agent_registry import AgentRegistry

from google.adk.agents.llm_agent import Agent

from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

# Load environment variables from .env
load_dotenv(override=True)
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
MCP_SERVER_NAME = os.environ.get("MCP_SERVER_NAME")

# Initialize the registry client
# https://adk.dev/integrations/agent-registry/
registry = AgentRegistry(
    project_id=PROJECT_ID,
    location=LOCATION,
)

# Retrieve an MCP toolset using its resource name in short or full format
# Google Cloud Console 의 Agent Registry 에서 MCP 를 선택해서 들어가면 샘플 코드 존재
# https://adk.dev/integrations/agent-registry/#use-with-agent
mcp_toolset = registry.get_mcp_toolset(mcp_server_name=MCP_SERVER_NAME)

# [Option 1 for Memory] 최근 발생한 이벤트의 일부(코드 설정 가능)를 Memory 에 전달 (권장방식)
# 최근 발생한 턴의 대화 맥락만 전달하여 새롭게 추가된 사실/선호도만 점진적으로 반영하기 위한 목적으로 적합 (매 턴 호출 권장)
# https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/adk-quickstart#manage-memories
async def add_events_to_memory_callback(callback_context: CallbackContext):
    # 세션의 전체 대화 이벤트 중 '최근 4개의 이벤트(뒤에서 5번째부터 1번째 까지 선택)'만을 선택하여 Memory Bank에 전달하겠다는 의미
    await callback_context.add_events_to_memory(events=callback_context.session.events[-5:-1])
    return None

root_agent = Agent(
    name="cloud_logging_agent",
    model="gemini-3.8-flash",
    instruction=(
        "You are an AI logging agent who can answer questions.\n"
        "Your target Google Cloud Project ID is '{project_id?}'.\n"
        "If the target project_id is empty, None, or not set, politely ask the user to provide their Google Cloud Project ID first. "        
    ),
    after_agent_callback=add_events_to_memory_callback,
    tools=[mcp_toolset, PreloadMemoryTool()]
)