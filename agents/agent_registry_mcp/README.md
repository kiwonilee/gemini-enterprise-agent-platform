# 📊 Agent Registry MCP 연동 에이전트 (`agent_registry_mcp`)

Google Cloud **Agent Registry**에 등록된 Cloud Logging MCP 서버(`logging.googleapis.com`)를 도구로 연동하여 프로젝트의 에러 로그를 조회·분석하는 에이전트입니다.

> **사전 준비**: 최초 1회 루트 디렉토리에서 `uv sync`, 루트 `.env` 생성 및 `bash scripts/setup_iam.sh` 실행을 완료해 주세요. (상세 내용은 [루트 README.md](../../README.md) 참고)

---

## ⚙️ 1. 에이전트 특화 설정 (MCP 서버 등록)

* **사용 서비스 계정**: `sa-agent-platform@${PROJECT_ID}.iam.gserviceaccount.com` (통합 서비스 계정)
  - 필수 역할: `roles/agentregistry.viewer`, `roles/mcp.toolUser`, `roles/logging.viewer`, `roles/logging.logWriter`, `roles/aiplatform.user`, `roles/storage.objectAdmin`, `roles/cloudtrace.user` (`scripts/setup_iam.sh` 실행 시 자동 생성·부여됨)
* **`MCP_SERVER_NAME` 환경 변수 등록**:
  Agent Registry에서 `logging.googleapis.com` MCP 서버의 리소스 이름을 조회하여 루트 `.env`(또는 현재 폴더의 `.env`)에 추가합니다.

```bash
export PROJECT_ID=$(gcloud config get-value project)
export MCP_ID=$(gcloud alpha agent-registry mcp-servers list \
    --location=global \
    --filter="displayName:logging.googleapis.com" \
    --format="value(name.basename())")

echo "MCP_SERVER_NAME=\"projects/${PROJECT_ID}/locations/global/mcpServers/${MCP_ID}\"" >> "$(git rev-parse --show-toplevel)/.env"
```

---

## 🚀 2. 에이전트 배포

```bash
cd "$(git rev-parse --show-toplevel)/agents/agent_registry_mcp"
uv run adk run .                   # 로컬 CLI 대화형 테스트 (선택)
uv run python agent_runtime.py     # 원격 Agent Runtime 배포
```

---

## 🔍 3. 테스트

### 방법 A: 자동화 스크립트로 테스트
```bash
"$(git rev-parse --show-toplevel)/scripts/test_all.sh" agent_registry_mcp
```

### 방법 B: `curl`로 직접 호출 테스트
```bash
export REASONING_ENGINE_ID="[배포 후 발급받은 REASONING_ENGINE_ID]"
export PROJECT_ID=$(gcloud config get-value project)
export PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")

# 1. 세션 생성
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/${PROJECT_NUMBER}/locations/us-central1/reasoningEngines/${REASONING_ENGINE_ID}:query" \
  -d '{"class_method": "create_session", "input": {"user_id": "test_user"}}'

# 2. 스트리밍 질의 실행
export SESSION_ID="[위 단계에서 발급받은 SESSION_ID]"
export MESSAGE="현재 project 는 ${PROJECT_ID} 이다. 최근 발생한 에러로그 5개를 분석해줘."

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
