# 🌤️ Agent Runtime (Agent Identity & Memory Bank)

날씨(`get_weather`)와 현재 시간(`get_current_time`) 조회 도구를 탑재하고, **Agent Identity (`AGENT_IDENTITY`)** 및 **Memory Bank (`PreloadMemoryTool`)**를 연동한 기본 에이전트입니다.

> **사전 준비**: 최초 1회 루트 디렉토리에서 `uv sync` 및 루트 `.env` 설정을 완료해 주세요. (상세 내용은 [루트 README.md](../../README.md) 참고)

---

## 🚀 1. 에이전트 배포

해당 에이전트 폴더로 이동하여 배포합니다.

```bash
cd ${ROOT_DIR}/agents/agent_runtime
uv run python agent_runtime.py
```

* 배포가 완료되면 콘솔에 **Remote Agent Name**과 **Agent Identity (`effective_identity`)** 및 권한 부여 명령어가 출력됩니다.

---

## 🔑 2. Agent Identity 권한 설정 (최초 배포 시 1회)

이 에이전트는 별도의 서비스 계정(SA) 대신 Google Cloud가 관리하는 **Agent Identity (`principal://...`)**를 사용합니다. 배포 직후 출력된 `AGENT_IDENTITY` 값으로 프로젝트 IAM 권한을 부여합니다.

```bash
export PROJECT_ID=$(gcloud config get-value project)
export AGENT_IDENTITY="[배포 결과에 출력된 effective_identity 값]"

ROLES=(
    "roles/aiplatform.user"
    "roles/aiplatform.viewer"
    "roles/serviceusage.serviceUsageConsumer"
    "roles/apptopology.viewer"
    "roles/agentregistry.viewer"
    "roles/cloudtrace.user"
    "roles/logging.logWriter"
    "roles/logging.viewer"
)

for ROLE in "${ROLES[@]}"; do
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
        --member="principal://${AGENT_IDENTITY}" \
        --role="${ROLE}"
done
```

---

## 🔍 3. 테스트

### 방법 A: 자동화 스크립트로 테스트
```bash
${ROOT_DIR}/scripts/test_all.sh agent_runtime
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

curl -s -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/${PROJECT_NUMBER}/locations/us-central1/reasoningEngines/${REASONING_ENGINE_ID}:streamQuery" \
  -d '{
    "class_method": "async_stream_query",
    "input": {
      "user_id": "test_user",
      "session_id": "'"${SESSION_ID}"'",
      "message": "뉴욕의 현재 날씨와 현재 시간을 알려줘."
    }
  }' | jq '.'
```
