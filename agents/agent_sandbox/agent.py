import os
from dotenv import load_dotenv
from google.adk.agents.llm_agent import Agent
from google.adk.code_executors.agent_engine_sandbox_code_executor import AgentEngineSandboxCodeExecutor

# Load environment variables from .env
load_dotenv(override=True)
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

class DummyLock:
    """threading.Lock의 피클링 불가능 이슈를 우회하기 위한 직렬화 가능 더미 락 컨텍스트 매니저"""
    def __enter__(self): pass
    def __exit__(self, exc_type, exc_val, exc_tb): pass


# 1. 네이티브 샌드박스 실행기 생성 (세션별 샌드박스 동적 생성)
code_executor = AgentEngineSandboxCodeExecutor()
code_executor._location = os.environ.get("GCP_RESOURCES_LOCATION", "us-central1")

# 2. 직렬화 충돌을 야기하는 threading.Lock 객체를 피클링이 잘 되는 DummyLock으로 치환
code_executor._agent_engine_creation_lock = DummyLock()

# 3. 가장 정석적이고 심플한 에이전트 정의
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