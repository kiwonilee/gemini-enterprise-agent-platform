# 📓 Jupyter Notebook 실습 및 평가 환경 (`notebooks/`)

Vertex AI Agent Runtime 배포와 Agent Evaluation(품질 플라이휠)을 Jupyter 노트북 환경에서 단계별로 실습할 수 있는 디렉토리입니다.

> **사전 준비**: 최상위 루트 디렉토리(`${ROOT_DIR}`)에서 `uv sync`, 루트 `.env` 생성 및 `bash scripts/setup_iam.sh` 실행을 완료해 주세요. (상세 내용은 [루트 README.md](../README.md) 참고)

---

## ⚙️ 1. 노트북 공통 실행 방법 (Jupyter 커널 선택)

루트 디렉토리에서 `uv sync`를 실행하면 루트 `.venv`에 `google-cloud-aiplatform[adk,agent_engines,evaluation]`, `ipykernel`, `pandas`, `matplotlib`가 모두 설치됩니다.

1. VS Code / Cloud Shell Editor / Jupyter에서 아래 노트북 파일을 엽니다.
2. 우측 상단 **Select Kernel(커널 선택)**에서 루트 가상환경(`${ROOT_DIR}/.venv/bin/python`)을 선택합니다.
3. 노트북 내부의 `load_dotenv(override=True)`가 상위 루트 `.env` 파일(`GOOGLE_CLOUD_PROJECT`, `GCP_RESOURCES_LOCATION`, `STAGING_BUCKET_URI`, `SERVICE_ACCOUNT`, `GEMINI_MODEL`)을 자동으로 불러옵니다.

---

## 📂 2. 노트북 목록

### ① [`agent_runtime.ipynb`](agent_runtime.ipynb) — Agent Runtime 배포 및 스트리밍 호출 실습
- 환율 조회 도구(`get_exchange_rate`)를 가진 ADK 에이전트를 정의하고, `client.runtimes.create()`로 **Vertex AI Agent Runtime**에 배포한 뒤 `remote_agent.async_stream_query()`로 실시간 질의를 수행합니다.

### ② [`agent_eval_local.ipynb`](agent_eval_local.ipynb) — Agent Evaluation (품질 평가) 실습
- 로컬 ADK 에이전트(`ecommerce_agent`)를 대상으로 **Vertex AI Evaluation (`client.evals`)**을 사용해 추론 실행(`run_inference`)부터 루브릭 기반 자동 채점(`create_evaluation_run`) 및 리포트 출력까지 수행합니다.

---

## 💡 3. 에이전트 평가(Evaluation) 라이프사이클 개요

**"① 시험 문제집(데이터셋)을 만들고 ➔ ② 에이전트에게 시험을 보게 한 뒤(추론/기록) ➔ ③ 채점관(LLM Judge)이 풀이 과정과 정답을 채점(평가)"**하는 일련의 라이프사이클입니다.

일반적인 텍스트 LLM은 `질문 ➔ 답변`만 채점하면 되지만, **에이전트(Agent)**는:
- 사용자의 질문을 듣고 어떤 도구(Tool)를 골랐는가?
- 도구에 들어갈 파라미터(인수)를 정확하게 추출했는가?
- 도구가 반환한 결과를 보고 다음 단계로 올바르게 판단했는가?

이러한 **'중간 풀이 과정(도구 호출 내역, Traces)'**이 에이전트 품질의 핵심을 결정합니다. 따라서 `client.evals.run_inference()`를 통해 **에이전트가 실제로 행동하는 모든 과정을 기록하여 데이터셋에 담아두는 작업(Inference)**이 선행된 후 `client.evals.create_evaluation_run()`으로 채점을 수행합니다.

### 주요 평가 도구 비교
1. **`agents-cli eval` (로컬 중심 빠른 반복 — Inner Development Loop)**
   - `tests/eval/evalsets/` 및 `tests/eval/eval_config.json` 기반으로 `agents-cli eval run` 명령어 하나로 추론과 채점을 즉각 실행합니다.
   - `agents-cli eval compare`를 통해 프롬프트/코드 수정 전후의 지표 변화와 궤적(trajectory)을 CLI에서 바로 대조할 수 있습니다.
2. **Agent Platform SDK (`client.evals` — 풀스택 품질 플라이휠)**
   - 시나리오 합성(`generate_conversation_scenarios`) ➔ 추론 실행(`run_inference`) ➔ 자동 채점(`create_evaluation_run` / `evaluate`) ➔ 실패 클러스터링(`generate_loss_clusters`) ➔ 프롬프트 최적화(`client.optimizer.optimize`)까지 전체 라이프사이클을 API로 제공합니다.
