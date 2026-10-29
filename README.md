# [Gemini Enterprise Agent Platform](https://docs.cloud.google.com/gemini-enterprise-agent-platform/overview)

## 🏛️ 1. 아키텍처 및 UV Workspace 구조

```text
gemini-enterprise-agent-platform/
├── .env.template                 # 환경 변수 템플릿
├── pyproject.toml                # 루트 UV Workspace 설정 (Python 3.11, ADK 2.13+)
├── agents/                       # 🚀 Agent Runtime 배포 대상 에이전트 패키지 (ADK 모듈 규칙에 따라 _ 사용)
│   ├── agent_runtime/            # 기본 에이전트 (Agent Identity + Memory Bank)
│   ├── agent_registry_mcp/       # Agent Registry MCP 연동 에이전트
│   ├── agent_sandbox/            # Agent Sandbox 격리 코드 실행 에이전트
│   ├── agent_skills/             # Skill Registry 플레이북 검색·로드 에이전트
│   └── graph_workflow/           # ADK 2.0 Graph Workflow + HITL 컨시어지 에이전트
├── notebooks/                    # 📓 Jupyter Notebook 실습 및 평가 환경
│   ├── README.md                 # 노트북 실행 가이드 및 평가 아키텍처 개요
│   ├── agent_runtime.ipynb       # Agent Runtime 배포 및 스트리밍 호출 실습
│   └── agent_eval_local.ipynb    # Agent Evaluation (품질 플라이휠) 실습
└── scripts/                      # 🛠️ 일괄 환경 구성, 테스트 및 리소스 정리 스크립트
    ├── setup_iam.sh              # API 활성화, GCS 버킷 및 통합 서비스 계정(sa-agent-platform)/IAM 일괄 설정
    ├── test_all.sh               # 전체(또는 개별) 에이전트 End-to-End 자동화 테스트
    └── cleanup_all.sh            # 배포된 Reasoning Engine, Sandbox, 서비스 계정(SA) 및 IAM 일괄 정리
```

### 📦 구성 에이전트 패키지 (`agents/`)
1. 📊 **[`agents/agent_registry_mcp`](agents/agent_registry_mcp/README.md)**
   - **역할**: Agent Registry에 등록된 MCP를 연동하여 데이터를 분석하는 에이전트
   - **핵심 기능**: `Agent Registry` \| `MCP Integration` \| `Agent Runtime` \| `Memory Service` \| `Agent Observability`

2. 🌤️ **[`agents/agent_runtime`](agents/agent_runtime/README.md)**
   - **역할**: 날씨, 시간 등 공통 시스템 도구를 탑재한 기본 실행 에이전트
   - **핵심 기능**: `Agent Runtime` \| `Agent Identity` \| `Memory Service`

3. 🛡️ **[`agents/agent_sandbox`](agents/agent_sandbox/README.md)**
   - **역할**: 생성된 코드를 격리된 환경에서 안전하게 실행할 수 있도록 돕는 샌드박스 에이전트
   - **핵심 기능**: `Agent Sandbox` \| `Agent Runtime` \| `Memory Service` \| `Default Agent SA`

4. 📚 **[`agents/agent_skills`](agents/agent_skills/README.md)**
   - **역할**: Skill Registry에서 적절한 스킬(플레이북)을 검색하여 작업을 수행하는 에이전트
   - **핵심 기능**: `Skill Registry` \| `Agent Runtime` \| `Agent Identity`

5. 🔄 **[`agents/graph_workflow`](agents/graph_workflow/README.md)**
   - **역할**: ADK 2.0 Graph Workflow 및 HITL(Human-In-The-Loop) 기반 인터랙티브 컨시어지 에이전트
   - **핵심 기능**: `Graph Workflow` \| `HITL (RequestInput / Resume)` \| `Agent Runtime`

### 📓 실습 및 평가 노트북 (`notebooks/`)
6. 📓 **[`notebooks/`](notebooks/README.md)** ([`agent_runtime.ipynb`](notebooks/agent_runtime.ipynb), [`agent_eval_local.ipynb`](notebooks/agent_eval_local.ipynb))
   - **역할**: 노트북 기반 Agent Runtime 실습 및 Agent Evaluation(품질 플라이휠) 환경

---

## 🧭 2. 실행 가이드

### Step 1. 저장소 클론 및 루트 경로 환경 변수(`ROOT_DIR`) 설정
이후 어느 디렉토리로 이동하든 루트 경로를 바로 참조할 수 있도록 `ROOT_DIR` 환경 변수를 먼저 지정합니다.

```bash
git clone https://github.com/kiwonilee/gemini-enterprise-agent-platform.git
cd gemini-enterprise-agent-platform

export ROOT_DIR=$(pwd)
```

### Step 2. 루트 폴더에서 최초 1회 공통 설정
어느 에이전트를 실행·배포하든 아래 3가지는 **최상위 루트 경로(`${ROOT_DIR}`)에서 최초 1회만** 실행하면 됩니다.
환경 변수 설정
```bash
export PROJECT_ID="YOUR_PROJECT_ID"
export STAGING_BUCKET_URI="gs://adk-${PROJECT_ID}"
```
```bash
cd ${ROOT_DIR}

# ① 통합 가상환경(.venv) 생성 및 모든 에이전트 패키지 한 번에 설치
uv sync
```
```bash
# ② 루트에 .env 파일 1개 생성 (하위 에이전트들이 자동으로 상위 .env 참조)
sed -e "s|your-project-id|${PROJECT_ID}|g" \
    -e "s|gs://your-gcs-bucket|${STAGING_BUCKET_URI}|g" \
    ${ROOT_DIR}/.env.template > ${ROOT_DIR}/.env

# ③ GCP API 활성화, GCS 버킷 생성, 통합 서비스 계정(sa-agent-platform) 및 IAM 권한 일괄 설정
bash ${ROOT_DIR}/scripts/setup_iam.sh
```

### 💻 (선택) 로컬에서 에이전트 실행
원격 배포 전에 로컬 터미널(CLI)이나 브라우저(Web UI)에서 에이전트를 바로 테스트할 수 있습니다.

```bash
# (Cloud Shell Web Preview 등 프록시 환경에서 JS 모듈 403 오류 방지를 위해 --allow_origins "*" 포함)
cd ${ROOT_DIR} && uv run adk web --allow_origins "*" agents
```

---

## 🚀 3. Step 3: Agent Runtime 에 원격 배포 (개별 에이전트 폴더 진입)

에이전트 배포는 개벌 폴더에서 직접 배포합니다.


