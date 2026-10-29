# 📓 Agent Runtime 배포 실습 노트북 (`agent_runtime.ipynb`)

Jupyter 노트북 환경에서 환율 조회 도구(`get_exchange_rate`)를 가진 ADK 에이전트를 정의하고, **Vertex AI Agent Runtime (`client.runtimes.create`)**에 배포 및 스트리밍 질의(`async_stream_query`)를 수행하는 실습 노트북입니다.

> **사전 준비**: 최상위 루트 디렉토리(`${ROOT_DIR}`)에서 `uv sync`, 루트 `.env` 생성 및 `bash scripts/setup_iam.sh` 실행을 완료해 주세요. (상세 내용은 [루트 README.md](../../README.md) 참고)

---

## ⚙️ 노트북 실행 방법

1. 루트 디렉토리에서 `uv sync`를 실행하면 루트 `.venv`에 `google-cloud-aiplatform[adk,agent_engines]`, `ipykernel` 등 필요한 패키지가 모두 설치됩니다.
2. VS Code / Cloud Shell Editor / Jupyter에서 [`agent_runtime.ipynb`](agent_runtime.ipynb) 파일을 엽니다.
3. 우측 상단 **Select Kernel(커널 선택)**에서 루트 가상환경(`${ROOT_DIR}/.venv/bin/python`)을 선택합니다.
4. 노트북 내부의 `load_dotenv(override=True)`가 상위 루트 `.env` 파일(`GOOGLE_CLOUD_PROJECT`, `GCP_RESOURCES_LOCATION`, `STAGING_BUCKET_URI`, `SERVICE_ACCOUNT`, `GEMINI_MODEL`)을 자동으로 불러와 배포에 사용합니다.
