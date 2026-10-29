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
import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

from google.adk.agents import Agent

from google.adk.agents.callback_context import CallbackContext
# from google.adk.tools.load_memory_tool import LoadMemoryTool
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

# Load environment variables from .env
load_dotenv(override=True)
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")


def get_weather(city: str) -> dict:
    if city.lower() == "new york":
        return {
            "status": "success",
            "report": "The weather in New York is sunny with a temperature of 25 degrees Celsius (77 degrees Fahrenheit).",
        }
    else:
        return {
            "status": "error",
            "error_message": f"Weather information for '{city}' is not available.",
        }


def get_current_time(city: str) -> dict:
    if city.lower() == "new york":
        tz_identifier = "America/New_York"
    else:
        return {
            "status": "error",
            "error_message": f"Sorry, I don't have timezone information for {city}.",
        }

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    report = f"The current time in {city} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"
    return {"status": "success", "report": report}


# [Option 1 for Memory] 최근 발생한 이벤트의 일부(코드 설정 가능)를 Memory 에 전달 (권장방식)
# 최근 발생한 턴의 대화 맥락만 전달하여 새롭게 추가된 사실/선호도만 점진적으로 반영하기 위한 목적으로 적합 (매 턴 호출 권장)
# https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/adk-quickstart#manage-memories
async def add_events_to_memory_callback(callback_context: CallbackContext):
    # 세션의 전체 대화 이벤트 중 '최근 4개의 이벤트(뒤에서 5번째부터 1번째 까지 선택)'만을 선택하여 Memory Bank에 전달하겠다는 의미
    await callback_context.add_events_to_memory(events=callback_context.session.events[-5:-1])
    return None

# [Option 2 for Memory] 세션에 포함된 모든 이벤트를 항상 Memory 에 저장, 이미 처리 했던 대화 이벤트도 중복 전달
# 세션 전체의 시작부터 끝까지의 흐름을 한눈에 볼 수 있어, 세션 전반에 걸쳐 분산된 복합적인 맥락을 한 번에 정리하기 좋기 때문에 세션이 완전히 끝난 후 세션 정리용으로 적합 (세션 종료 시점에 호출 권장)
# https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/adk-quickstart#manage-memories
# async def add_session_to_memory_callback(callback_context: CallbackContext):
#     await callback_context.add_session_to_memory()
#     return None


root_agent = Agent(
    name="weather_time_agent",
    model=GEMINI_MODEL,
    description="Agent to answer questions about the time and weather in a city.",
    instruction="You are a helpful agent who can answer user questions about the time and weather in a city.",
    after_agent_callback=add_events_to_memory_callback,    

    # [Option 1 for Memory] 매 턴의 시작 시점에 무조건 호출 (https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/adk-quickstart#define_a_memory_retrieval_tool)
    tools=[get_weather, get_current_time, PreloadMemoryTool()],

    # [Option 2 for Memory] 모델이 판단하여 필요하다고 결정할때만 호출 (https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/adk-quickstart#define_a_memory_retrieval_tool)
    # tools=[get_weather, get_current_time, LoadMemoryTool()],
)
