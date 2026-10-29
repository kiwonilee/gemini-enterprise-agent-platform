# 🔄 ADK 2.0 Graph Workflow & HITL 컨시어지 에이전트 (`graph_workflow`)

ADK 2.0의 **Graph Workflow (`Workflow`)**와 **Human-In-The-Loop (`RequestInput`)** 기능을 활용하여 사용자의 여행 선호도를 입력받고, 피드백 루프(`process_feedback` ➔ `concierge_agent`)를 통해 맞춤형 여행 일정을 반복 수정하는 대화형 에이전트입니다.

> **사전 준비**: 최초 1회 루트 디렉토리에서 `uv sync`, 루트 `.env` 생성 및 `bash scripts/setup_iam.sh` 실행을 완료해 주세요. (상세 내용은 [루트 README.md](../../README.md) 참고)

---

## 💡 1. Graph Workflow & HITL 설계 원리

1. **그래프 실행 흐름 (`edges`)**:
   - 초기 흐름: `START` ➔ `initial_prompt` (HITL 1 대기) ➔ `concierge_agent` (5개 여행 일정 생성) ➔ `get_user_feedback` (HITL 2 대기) ➔ `process_feedback`
   - 피드백 순환 루프: `process_feedback` ➔ `{"loop": concierge_agent}` (사용자 피드백을 반영해 일정 재생성 후 다시 피드백 대기)
2. **HITL 재개(Resume) 프로토콜**:
   - `RequestInput`으로 일시 정지(Paused)된 노드를 재개할 때는 일반 텍스트 메시지 대신, 이전 응답의 `adk_request_input` 함수 호출에서 반환된 고유 **`interruptId`**를 `function_response` 페이로드의 `id`에 매핑하여 전달해야 합니다.

---

## 🚀 2. 에이전트 배포

```bash
cd ${ROOT_DIR}/agents/graph_workflow
uv run python agent_runtime.py
```

---

## 🔍 3. 멀티턴 HITL 테스트

### `curl`로 단계별 직접 호출 테스트

#### 1️⃣ 세션 생성
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

#### 2️⃣ [Case 1] 일정 추천 서비스 시작 (첫 번째 HITL 대기)
```bash
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
      "message": "여행 일정 추천 서비스를 시작해줘."
    }
  }' | jq '.'
```

#### 3️⃣ [Case 2] 여행 선호도 전달 및 일정 생성 (두 번째 HITL 대기)
```bash
export INTERRUPT_ID="[Case 1 응답의 adk_request_input args.interruptId 값]"
export MESSAGE="도시: 서울, 연령대: 20대, 취미: 맛집 탐방 및 야간 사진 촬영, 좋아했던 관광지: 경복궁 야간 개장"

curl -s -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/${PROJECT_NUMBER}/locations/us-central1/reasoningEngines/${REASONING_ENGINE_ID}:streamQuery" \
  -d '{
    "class_method": "async_stream_query",
    "input": {
      "user_id": "test_user",
      "session_id": "'"${SESSION_ID}"'",
      "message": {
        "role": "user",
        "parts": [
          {
            "function_response": {
              "name": "adk_request_input",
              "id": "'"${INTERRUPT_ID}"'",
              "response": {
                "user response": "'"${MESSAGE}"'"
              }
            }
          }
        ]
      }
    }
  }' | jq '.'
```

#### 4️⃣ [Case 3] 피드백 루프백 및 일정 수정
```bash
export INTERRUPT_ID="[Case 2 응답의 adk_request_input args.interruptId 값]"
export MESSAGE="기본 추천 일정 중 2번 대신, 경복궁 야간 한복 체험 및 인생샷 명소 투어로 일정을 교체하고 상세 설명을 업데이트해줘."

curl -s -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/${PROJECT_NUMBER}/locations/us-central1/reasoningEngines/${REASONING_ENGINE_ID}:streamQuery" \
  -d '{
    "class_method": "async_stream_query",
    "input": {
      "user_id": "test_user",
      "session_id": "'"${SESSION_ID}"'",
      "message": {
        "role": "user",
        "parts": [
          {
            "function_response": {
              "name": "adk_request_input",
              "id": "'"${INTERRUPT_ID}"'",
              "response": {
                "user": "'"${MESSAGE}"'"
              }
            }
          }
        ]
      }
    }
  }' | jq '.'
```
