# 📓 Jupyter Notebook 실행 가이드 (`notebooks/`)

본 디렉토리에는 Vertex AI Agent Runtime 배포와 Agent Evaluation을 실습할 수 있는 2개의 노트북이 포함되어 있습니다:
- **[`agent_runtime.ipynb`](agent_runtime.ipynb)**: ADK 에이전트 정의 및 Agent Runtime 원격 배포·스트리밍 호출 실습
- **[`agent_eval_local.ipynb`](agent_eval_local.ipynb)**: Agent Platform SDK(`client.evals`) 기반 에이전트 추론 기록 및 루브릭 자동 채점 실습

---

## 💻 1. 로컬 환경 (VS Code / Cloud Shell Editor)에서 실행하기

최상위 루트 디렉토리(`${ROOT_DIR}`)에서 이미 [루트 README.md](../README.md)의 초기 설정(`uv sync`, `.env` 생성, `bash scripts/setup_iam.sh`)을 마쳤다면 별도 패키지 설치 없이 루트 가상환경(`.venv`)을 커널로 바로 연결해 사용할 수 있습니다.

1. 루트 디렉토리에서 통합 환경이 구성되어 있는지 확인합니다:
   ```bash
   cd ${ROOT_DIR}
   uv sync
   ```
2. VS Code 또는 Cloud Shell Editor에서 [`agent_runtime.ipynb`](agent_runtime.ipynb) 또는 [`agent_eval_local.ipynb`](agent_eval_local.ipynb) 파일을 엽니다.
3. 우측 상단 **Select Kernel(커널 선택)** ➔ **Python Environments** ➔ 루트 가상환경(`${ROOT_DIR}/.venv/bin/python`)을 선택합니다.
4. 첫 번째 `%pip install` 셀은 건너뛰어도 무방하며, 이후 셀들을 순서대로 실행합니다 (`load_dotenv(override=True)`가 상위 `${ROOT_DIR}/.env`를 자동으로 불러옵니다).

---

## ☁️ 2. Agent Platform AI Workbench 에서 실행하기

Google Cloud Console의 **Agent Platform Workbench** 인스턴스(JupyterLab)에서 실행하는 방법입니다.

### Step 1. JupyterLab 터미널에서 저장소 클론 및 `.env` 설정
Workbench의 JupyterLab 런처에서 **Terminal**을 열고 아래 명령어를 실행합니다:

```bash
git clone https://github.com/kiwonilee/gemini-enterprise-agent-platform.git
cd gemini-enterprise-agent-platform
export ROOT_DIR=$(pwd)

export PROJECT_ID=$(gcloud config get-value project)
export STAGING_BUCKET_URI="gs://adk-${PROJECT_ID}"

# 루트 .env 파일 생성
sed -e "s|your-project-id|${PROJECT_ID}|g" \
    -e "s|gs://your-gcs-bucket|${STAGING_BUCKET_URI}|g" \
    ${ROOT_DIR}/.env.template > ${ROOT_DIR}/.env

# API 활성화, GCS 버킷 및 통합 서비스 계정(sa-agent-platform) 설정
bash ${ROOT_DIR}/scripts/setup_iam.sh
```

### Step 2. 노트북 열기 및 패키지 설치 후 실행
1. 좌측 파일 브라우저에서 `gemini-enterprise-agent-platform/notebooks/` 폴더로 이동하여 원하는 `.ipynb` 파일을 엽니다 (기본 **Python 3 (ipykernel)** 선택).
2. 노트북 최상단의 **`%pip install ...` 코드 셀을 실행**하여 현재 Workbench 커널에 최신 `google-cloud-aiplatform[adk,agent_engines,evaluation]` 패키지를 설치합니다.
3. 패키지 설치 완료 후 상단 메뉴에서 **Kernel ➔ Restart Kernel**을 한 번 실행한 뒤, 아래 셀들을 순서대로 실행합니다.
