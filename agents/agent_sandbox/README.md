# 🛡️ Agent Sandbox 코드 실행 에이전트 (`agent_sandbox`)

생성된 파이썬 코드를 격리된 보안 환경인 **Vertex AI 관리형 샌드박스(`AgentEngineSandboxCodeExecutor`)**에서 실행하고 결과를 분석하는 에이전트입니다.

> **사전 준비**: 최초 1회 루트 디렉토리에서 `uv sync`, 루트 `.env` 생성 및 `bash scripts/setup_iam.sh` 실행을 완료해 주세요. (상세 내용은 [루트 README.md](../../README.md) 참고)

---

## ⚙️ 1. 에이전트 특화 동작 방식

* **사용 서비스 계정**: `sa-agent-platform@${PROJECT_ID}.iam.gserviceaccount.com` (통합 서비스 계정)
* **세션별 샌드박스 동적 프로비저닝**:
  1. `AgentEngineSandboxCodeExecutor()`에 고정 샌드박스 경로를 지정하지 않아, 대화 세션에서 최초로 파이썬 코드를 실행할 때 **세션 전용 관리형 샌드박스(`sandboxEnvironments`)가 자동으로 생성**됩니다.
  2. 생성된 샌드박스 경로는 `session.state['sandbox_name']`에 저장되어, **동일 세션 내 연속 질문에서는 기존 샌드박스(변수·파일 상태)가 그대로 재사용**되고 다른 세션과는 완벽히 격리됩니다.

---

## 🚀 2. 에이전트 배포

```bash
cd ${ROOT_DIR}/agents/agent_sandbox
uv run python agent_runtime.py
```

---

## 🔍 3. 테스트

### `curl`로 직접 호출 테스트
```bash
export REASONING_ENGINE_ID="[배포 후 발급받은 REASONING_ENGINE_ID]" #경로를 제외한 숫자로만 된 부분
export PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format="value(projectNumber)")

# 1. 세션 생성
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/${PROJECT_NUMBER}/locations/us-central1/reasoningEngines/${REASONING_ENGINE_ID}:query" \
  -d '{"class_method": "create_session", "input": {"user_id": "test_user"}}'
```
```bash
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

응답결과
```json
...
"executable_code": {
  "code": "def is_prime(n):\n ... \nprint(f\"소수의 개수: {len(primes)}개\")",
  "language": "PYTHON"
}
...
"code_execution_result": {
  "outcome": "OUTCOME_OK",
  "output": "Code execution result:\n소수 목록: [2, 3, ..., 97]\n소수의 개수: 25개\n\n"
},
...
"actions": {
  "state_delta": {
    "_code_execution_context": {
      "sandbox_name": "projects/66073569876/locations/us-central1/reasoningEngines/1866612578050899968/sandboxEnvironments/5985432888600952832"
    }
  }
}
```
