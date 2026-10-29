# 📚 Skill Registry 연동 에이전트 (`agent_skills`)

Google Cloud **Skill Registry**에서 사용자 질의에 부합하는 스킬(플레이북)을 검색(`search_skills`) 및 로드(`load_skill`)하여 표준 가이드에 기반한 답변을 제공하는 에이전트입니다.

> **사전 준비**: 최초 1회 루트 디렉토리에서 `uv sync`, 루트 `.env` 생성 및 `bash scripts/setup_iam.sh` 실행을 완료해 주세요. (상세 내용은 [루트 README.md](../../README.md) 참고)

---

## ⚙️ 1. 에이전트 특화 구성

* **사용 서비스 계정**: `sa-agent-platform@${PROJECT_ID}.iam.gserviceaccount.com` (통합 서비스 계정)
  - 필수 역할: `roles/agentregistry.viewer`, `roles/aiplatform.user`, `roles/serviceusage.serviceUsageConsumer`, `roles/logging.viewer`, `roles/logging.logWriter`, `roles/cloudtrace.user` (`scripts/setup_iam.sh` 실행 시 자동 생성·부여됨)
* **키워드 검색 및 폴백 (`KeywordGCPSkillRegistry`)**:
  `agent.py` 내 `KeywordGCPSkillRegistry`를 통해 `KEYWORD` 검색 모드 및 다중 단어 `OR` 폴백 정렬을 수행하여 `cloud.google.com-*` 1P 스킬 및 커스텀 스킬을 안정적으로 탐색합니다.

---

## 🚀 2. 에이전트 배포

```bash
cd ${ROOT_DIR}/agents/agent_skills
uv run python agent_runtime.py
```

---

## 🔍 3. 테스트

### 방법 A: 자동화 스크립트로 테스트
```bash
${ROOT_DIR}/scripts/test_all.sh agent_skills
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
export MESSAGE="GKE 의 Cluster Upgrade 에 대한 Best Practice 에 대해서 알려줘"

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

## 🛠️ 4. Skill Registry 관리 CLI 도구 (`skill_registry.py`)

원격 스킬 레지스트리 내의 플레이북을 등록, 조회, 삭제 및 검색 테스트할 때 사용하는 관리 CLI 도구입니다.

```bash
# A. 등록된 전체 플레이북 스킬 리스트 조회
uv run python skill_registry.py list

# B. 신규 플레이북 스킬 생성 및 등록
uv run python skill_registry.py create \
    --display-name "GKE Node Upgrade Playbook" \
    --description "Step-by-step handbook to perform safe GKE node upgrades" \
    --local-path "path/to/playbooks/gke_upgrade"

# C. 특정 플레이북 스킬 세부 명세 조회
uv run python skill_registry.py get --skill-name "[스킬ID 또는 리소스 고유URI]"

# D. 등록된 스킬 삭제
uv run python skill_registry.py delete --skill-name "[스킬ID 또는 리소스 고유URI]"

# E. 플레이북 지식 검색 테스트
uv run python skill_registry.py retrieve --query "GKE node upgrade" --top-k 2

# F. GitHub 리포지토리로부터 플레이북 스킬 벌크 임포트
uv run python skill_registry.py import --github-url "https://github.com/google/skills"
```
