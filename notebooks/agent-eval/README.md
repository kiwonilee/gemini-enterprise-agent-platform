# 📓 Agent Evaluation 실습 노트북 (`agent_eval_local.ipynb`)

로컬 ADK 에이전트를 대상으로 **Vertex AI Evaluation (`client.evals`)**을 사용해 추론 실행(`run_inference`)부터 루브릭 기반 자동 채점(`create_evaluation_run`)까지 수행하는 실습 노트북입니다.

> **사전 준비**: 최상위 루트 디렉토리(`${ROOT_DIR}`)에서 `uv sync`, 루트 `.env` 생성 및 `bash scripts/setup_iam.sh` 실행을 완료해 주세요. (상세 내용은 [루트 README.md](../../README.md) 참고)

---

## ⚙️ 1. 노트북 실행 환경 (Jupyter 커널 선택)

루트 디렉토리에서 `uv sync`를 실행하면 루트 `.venv`에 `google-cloud-aiplatform[adk,agent_engines,evaluation]`, `ipykernel`, `pandas`, `matplotlib`가 모두 설치됩니다.

1. VS Code / Cloud Shell Editor / Jupyter에서 [`agent_eval_local.ipynb`](agent_eval_local.ipynb) 파일을 엽니다.
2. 우측 상단 **Select Kernel(커널 선택)**에서 루트 가상환경(`${ROOT_DIR}/.venv/bin/python`)을 선택합니다.
3. 노트북 내부의 `load_dotenv(override=True)`가 상위 루트 `.env` 파일(`GOOGLE_CLOUD_PROJECT`, `GCP_RESOURCES_LOCATION`, `STAGING_BUCKET_URI`, `GEMINI_MODEL`)을 자동으로 불러옵니다.

---

## 💡 2. 에이전트 평가 라이프사이클 개요

**"① 시험 문제집(데이터셋)을 만들고 ➔ ② 에이전트에게 시험을 보게 한 뒤(추론/기록) ➔ ③ 채점관(LLM Judge)이 풀이 과정과 정답을 채점(평가)"**하는 일련의 라이프사이클입니다.

일반적인 텍스트 LLM은 `질문 ➔ 답변`만 채점하면 되지만, **에이전트(Agent)**는:
- 사용자의 질문을 듣고 어떤 도구(Tool)를 골랐는가?
- 도구에 들어갈 파라미터(인수)를 정확하게 추출했는가?
- 도구가 반환한 결과를 보고 다음 단계로 올바르게 판단했는가?

이러한 **'중간 풀이 과정(도구 호출 내역, Traces)'**이 에이전트 품질의 핵심을 결정합니다. 따라서 `client.evals.run_inference()`를 통해 **에이전트가 실제로 행동하는 모든 과정을 기록하여 데이터셋에 담아두는 작업(Inference)**이 선행된 후 `client.evals.create_evaluation_run()`으로 채점을 수행합니다.

---

## 🔍 3. 주요 평가 도구 및 아키텍처 비교

### (1) `agents-cli eval`
- **로컬 중심 빠른 반복 (Inner Development Loop)**:
  - `agents-cli scaffold`로 생성된 표준 프로젝트 구조(`tests/eval/evalsets/`, `tests/eval/eval_config.json`)를 기반으로 작동합니다.
  - `agents-cli eval run` 명령어 하나로 시나리오 추론(`generate`)과 채점(`grade`)을 체이닝하여 즉각적인 결과를 출력합니다.
- **AI 코딩 에이전트와의 밀접한 통합**:
  - 코딩 에이전트가 평가 결과를 읽고 실패 원인을 분석하여 에이전트 프롬프트나 툴 코드를 즉시 수정하는 Eval-Fix Loop를 로컬에서 자율 수행하도록 최적화되어 있습니다.
- **회귀 테스트 및 결과 비교**:
  - `agents-cli eval compare`를 지원하여 프롬프트/코드 수정 전후의 지표 변화와 궤적(trajectory)을 CLI 상에서 바로 대조할 수 있습니다.

### (2) Agent Platform SDK (`client.evals`)
- **풀스택 품질 플라이휠 (Quality Flywheel)**:
  - 시나리오 합성 (`client.evals.generate_conversation_scenarios`): 사용자 시뮬레이션을 위한 멀티턴 테스트 케이스 자동 생성
  - 추론 실행 (`client.evals.run_inference`): 실행 추적(Trace) 및 도구 호출 캡처
  - 자동 채점 (`client.evals.create_evaluation_run` / `evaluate`): `FINAL_RESPONSE_QUALITY`, `TOOL_USE_QUALITY`, `HALLUCINATION`, `SAFETY` 등 AutoRater 및 LLM-as-a-judge 적용
  - 실패 클러스터링 (`client.evals.generate_loss_clusters`): 평가 실패 건들을 공통 오류 패턴별로 군집화
  - 프롬프트 자동 최적화 (`client.optimizer.optimize`): 실패 분석 결과를 기반으로 에이전트 시스템 프롬프트 자동 개선
- **프로덕션/대규모 환경 지원**:
  - 실제 운영 트래픽(Live production traces)에 대한 온라인 모니터링 및 Cloud 대규모 배치 평가 파이프라인에 직접 통합할 수 있습니다.
