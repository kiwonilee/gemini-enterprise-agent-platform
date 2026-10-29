import os
from typing import Any
from dotenv import load_dotenv
from google.adk.agents.llm_agent import LlmAgent
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.workflow import Workflow
from google.adk.agents.context import Context
from google.genai.types import UserContent
from pydantic import BaseModel

# Load environment variables from .env
load_dotenv(override=True)
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")


# --- Data classes ---
# LLM 에이전트가 최종적으로 생성해야 할 출력 데이터의 규격(스키마)을 Pydantic으로 강제합니다.
class Activity(BaseModel):
    name: str
    description: str


class ActivitiesList(BaseModel):
    """여행 일정은 각 활동에 대한 리스트여야 합니다. 각 활동은 이름과 설명을 가집니다."""

    itinerary: list[Activity]


# --- Agents ---
# 사용자의 입력을 바탕으로 맞춤형 활동 리스트를 생성하는 핵심 LLM 에이전트입니다.
concierge_agent = LlmAgent(
    name="concierge_agent",
    model=GEMINI_MODEL,
    instruction="""
        당신은 사용자의 입력을 기반으로 가고 싶은 도시에 맞는 맞춤형 여행 활동 일정을 계획하는 전문 컨시어지(concierge) 에이전트입니다.
        제공된 장소(도시)와 연령대, 취미 등의 정보를 바탕으로 사용자가 만족할 수 있는 다채롭고 구체적인 여행 활동 목록을 5개 이상 생성해 주세요.
        모든 이름과 설명은 친근한 한국어로 자세하게 작성해야 합니다.
    """,
    output_schema=ActivitiesList,
)


# --- Functions ---
# 워크플로우가 처음 시작될 때 실행되며, 사용자에게 초기 질문을 던지고 답변을 기다립니다.
async def initial_prompt(ctx: Context):
    """
    사용자에게 보여줄 초기 안내 메시지를 제공합니다.
    """
    input_message = """
        원하시는 도시에 맞는 멋진 여행 일정을 계획해 드리는 대화형 컨시어지 워크플로우입니다.
        자신에 대한 정보나 원하시는 스타일을 알려주시면, 더욱 개인화된 맞춤형 일정을 추천해 드릴 수 있습니다.
        예를 들어, 아래 정보를 입력해 주세요:
            도시 (필수),
            연령대,
            취미,
            좋아했던 관광지 예시
    """
    resp = {"user response": "response"}
    # Human input for agent workflow -  https://adk.dev/graphs/human-input/
    yield RequestInput(message=input_message, response_schema=resp)


# 생성된 일정을 사용자에게 보여주고, 피드백을 요청하여 워크플로우를 일시 중지(Pause)합니다.
async def get_user_feedback(node_input: ActivitiesList):
    """
    에이전트가 추천한 초기 일정에 대한 사용자의 의견을 수렴하여 일정을 확장, 변경하거나 루프를 종료합니다.
    """
    formatted_itinerary = ""
    if hasattr(node_input, "itinerary") and node_input.itinerary:
        for i, act in enumerate(node_input.itinerary, 1):
            formatted_itinerary += f"📌 {i}. {act.name}\n   - {act.description}\n\n"
    else:
        formatted_itinerary = "생성된 여행 일정이 없습니다.\n"

    message = f"""
        추천해 드리는 기본 여행 일정입니다:
        
{formatted_itinerary}
        이 중에서 어떤 활동이 마음에 드시나요? (또는 변경하고 싶은 부분이 있으신가요?)
        """

    # Human input for agent workflow -  https://adk.dev/graphs/human-input/
    yield RequestInput(
        message=message,
        payload=node_input,
        response_schema={"user": "response"},
    )


# 사용자가 입력한 피드백 문자열을 받아 LLM이 다음 노드에서 이해할 수 있는 메시지 형태(UserContent)로 가공합니다.
async def process_feedback(node_input: dict[str, Any] | str):
    if isinstance(node_input, dict):
        feedback_text = next(iter(node_input.values()), str(node_input))
    else:
        feedback_text = str(node_input)
    yield Event(
        content=UserContent(f"피드백: {feedback_text}."),
        output=f"피드백: {feedback_text}.",
        route="loop"
    )


# --- Workflow ---
# 위에서 정의한 에이전트와 함수들을 하나의 그래프 흐름으로 연결하는 메인 워크플로우입니다.
root_agent = Workflow(
    name="root_agent",
    rerun_on_resume=True,
    # 실행 흐름(Edges):
    # 1. 초기 순서: START ➔ initial_prompt ➔ concierge_agent ➔ get_user_feedback ➔ process_feedback
    # 2. 순환 루프: process_feedback ➔ concierge_agent (피드백을 반영하여 일정 무한 수정)
    edges=[
        (
            "START",
            initial_prompt,
            concierge_agent,
            get_user_feedback,
            process_feedback,
        ),
        (process_feedback, {"loop": concierge_agent}),
    ], # 2 nodes run in order
)