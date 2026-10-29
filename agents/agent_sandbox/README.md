# 🛡️ Agent Sandbox 코드 실행 에이전트 (`agent_sandbox`)

생성된 파이썬 코드를 격리된 보안 환경인 **Vertex AI 관리형 샌드박스(`AgentEngineSandboxCodeExecutor`)**에서 실행하고 결과를 분석하는 에이전트입니다.

> **사전 준비**: 최초 1회 루트 디렉토리에서 `uv sync`, 루트 `.env` 생성 및 `bash scripts/setup_iam.sh` 실행을 완료해 주세요. (상세 내용은 [루트 README.md](../../README.md) 참고)

---

## ⚙️ 1. 에이전트 특화 동작 방식

* **사용 서비스 계정**: `sa-agent-platform@${PROJECT_ID}.iam.gserviceaccount.com` (통합 서비스 계정)
* **샌드박스 자동 프로비저닝**:
  1. `.env`에 `SANDBOX_RESOURCE_NAME`이 설정되어 있으면 기존 샌드박스를 재사용합니다.
  2. 설정되어 있지 않으면 `agent_runtime.py`가 실행될 때 부모 컨테이너(`AgentEngine`)와 관리형 샌드박스(`sandboxEnvironments`)를 자동으로 생성한 뒤 `SANDBOX_RESOURCE_NAME`을 주입하여 배포합니다.

---

## 🚀 2. 에이전트 배포

```bash
cd "$(git rev-parse --show-toplevel)/agents/agent_sandbox"
uv run adk run .                   # 로컬 CLI 대화형 테스트 (선택)
uv run python agent_runtime.py     # 원격 Agent Runtime 배포
```

---

## 🔍 3. 테스트

### 방법 A: 자동화 스크립트로 테스트
```bash
"$(git rev-parse --show-toplevel)/scripts/test_all.sh" agent_sandbox
```

### 방법 B: `curl`로 직접 호출 테스트
```bash
export REASONING_ENGINE_ID="[배포 후 발급받은 REASONING_ENGINE_ID]"
export PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format="value(projectNumber)")

# 1. 세션 생성
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/${PROJECT_NUMBER}/locations/us-central1/reasoningEngines/${REASONING_ENGINE_ID}:query" \
  -d '{"class_method": "create_session", "input": {"user_id": "test_user"}}'

# 2. 스트리밍 질의 실행
export SESSION_ID="[위 단계에서 발급받은 SESSION_ID]"
export MESSAGE="1부터 100까지의 숫자 중 소수(Prime Number)의 개수를 구하는 파이썬 코드를 작성하고 실행 결과를 알려줘."

curl -s -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/${PROJECT_NUMBER}/locations/us-central1/reasoningEngines/${REASONING_ENGINE_ID}:streamQuery" \
  -d '{
    "class_method": "async_stream_query",
    "input": {
      "user_id": "test_user",
      "session_id": "'"${SESSION_ID}"'",
      "message": "'"${MESSAGE}"'"
    }
  }' | jq '.'
```

---

## 💡 4. 관리형 샌드박스 활용 추천 프롬프트 (4가지 핵심 Case)

1. **Case 1. 보안 격리 및 파일 생성 (Safe File I/O)**
   > "pandas를 사용하여 임의의 가상 직원 데이터(이름, 부서, 연봉, 입사일) 5행을 생성하고, 이를 'employees.csv' 파일로 저장한 뒤 표 형식으로 내용을 보여줘."
2. **Case 2. 다중 대화 상태 유지 (Multi-turn Session State)**
   - **질문 1**: `"먼저 파이썬 코드로 x = 10, y = 20을 선언하고 두 값을 더한 결과를 출력해줘."`
   - **질문 2 (연속 질문)**: `"방금 메모리에 선언된 x와 y의 합에 5를 곱한 값을 다시 파이썬 코드로 연산하고 최종 결과를 알려줘."`
3. **Case 3. 시각화 및 파일 아티팩트 보존 (Visualization & Artifacts)**
   > "2020년부터 2024년까지의 주요 빅테크 기업(Google, Apple, Microsoft)의 가상 주가 변동 추이를 pandas와 matplotlib을 사용해 선 그래프 차트로 그려주고, 이를 'stock_trends.png' 파일로 저장한 뒤 결과를 요약해줘."
4. **Case 4. 무거운 알고리즘 연산 및 비교 (Heavy Computation)**
   > "피보나치 수열의 35번째 값을 계산하는 단순 재귀 알고리즘과 메모이제이션 알고리즘의 파이썬 코드를 작성해줘. 그리고 time 모듈을 사용해서 두 방식의 실제 실행 시간 차이를 밀리초(ms) 단위로 비교해 알려줘."

---

## 💡 5. 대체 구성 참고: `BuiltInCodeExecutor` (경량 내장 실행기)

별도 샌드박스 리소스 생성 없이 Gemini 모델 내장 코드 실행기를 사용하려면 `agent.py`에서 `BuiltInCodeExecutor`로 교체할 수 있습니다:

```python
from google.adk.agents.llm_agent import Agent
from google.adk.code_executors.built_in_code_executor import BuiltInCodeExecutor

root_agent = Agent(
    model="gemini-3.8-flash",
    name="data_analyst",
    instruction="코드 실행기 도구를 사용하여 요청하신 연산을 수행하고 그 결과를 보고하세요.",
    code_executor=BuiltInCodeExecutor(),
)
```
