import contextlib
import os
from dotenv import load_dotenv
from google.adk.agents.llm_agent import Agent
from google.adk.code_executors.agent_engine_sandbox_code_executor import AgentEngineSandboxCodeExecutor

# Load environment variables from .env
load_dotenv(override=True)
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

# 1. 네이티브 샌드박스 실행기 생성 (세션별 샌드박스 동적 생성)
code_executor = AgentEngineSandboxCodeExecutor()
code_executor._location = os.environ.get("GCP_RESOURCES_LOCATION", "us-central1")

# 2. cloudpickle 직렬화 시 충돌하는 threading.Lock을 표준 nullcontext로 치환
code_executor._agent_engine_creation_lock = contextlib.nullcontext()

# 3. 에이전트 정의
root_agent = Agent(
    model=GEMINI_MODEL,
    name="agent_sandbox",
    instruction="""You are a simple assistant.
    If you need to run Python code, you MUST write the code directly inside a markdown code block (starting with ```python and ending with ```) in your response.
    The framework will automatically intercept the code, execute it in the managed sandbox, and provide the results back to you.
    Always explain the execution results clearly after you get them.
    """,
    code_executor=code_executor,
)
