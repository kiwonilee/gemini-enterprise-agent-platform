# 로컬 환경 세팅 - 노트북 실행에 사용할 Python 환경과 커널 패키지를 설치

```bash
# 1. 프로젝트 폴더로 이동 (루트에서 uv sync를 실행했다면 루트 .venv 커널을 바로 사용할 수 있습니다)
cd ~/workspace/gemini-enterprise-agent-platform/notebooks/agent-eval

# 2. uv로 가상환경 생성 (--seed 옵션을 추가해야 노트북 내에서 %pip 명령어가 동작합니다)
uv venv --seed .venv

# 3. ipykernel 및 Agent Platform 개발/평가에 필요한 라이브러리 일괄 설치
# (Google 사내 환경에서는 airlock-proxy 인덱스 지정 필요)
uv pip install \
  --index-url http://airlock-proxy.uplink.goog:999/python/artifact-foundry-prod/ah-3p-staging-python/simple/ \
  --allow-insecure-host airlock-proxy.uplink.goog \
  pip ipykernel numpy pandas matplotlib cloudpickle pydantic \
  "google-cloud-aiplatform[adk,agent_engines,evaluation]"
```

### 3. `.env` 파일 생성
부모 디렉토리의 환경 변수 템플릿(`.env.template`)을 참조하여 프로젝트 정보를 치환한 로컬 `.env` 파일을 생성합니다.

```bash
# 1. 환경 변수 템플릿을 치환하여 로컬 .env 생성 (notebooks/agent-eval 디렉토리 내부에서 실행, 루트 .env가 있으면 생략 가능)
sed -e "s|your-project-id|${PROJECT_ID}|g" \
    -e "s|your-gcs-bucket|${STAGING_BUCKET_URI}|g" \
    ../../.env.template > .env

# 2. 설정이 정상적으로 적용되었는지 확인
cat .env
```


**"① 시험 문제집(데이터셋)을 만들고 ➔ ② 에이전트에게 시험을 보게 한 뒤(추론/기록) ➔ ③ 채점관(LLM Judge)이 풀이 과정과 정답을 채점(평가)"**하는 일련의 라이프사이클

일반적인 텍스트 LLM은 질문 ➔ 답변만 채점하면 됩니다. 하지만 **에이전트(Agent)**는:

사용자의 질문을 듣고 어떤 도구(Tool)를 골랐는가?
도구에 들어갈 파라미터(인수)를 정확하게 추출했는가?
도구가 반환한 결과를 보고 다음 단계로 올바르게 판단했는가?
이러한 **'중간 풀이 과정(도구 호출 내역, Traces)'**이 에이전트 품질의 90% 이상을 결정합니다.
따라서 client.evals.run_inference()를 통해 **에이전트가 실제로 행동하는 모든 과정을 녹화하여 데이터셋에 담아두는 작업(Inference)**이 반드시 선행되어야 합니다.



2. 주요 기능 및 아키텍처 비교
(1) agents-cli eval
로컬 중심 빠른 반복 (Inner Development Loop):
agents-cli scaffold로 생성된 표준 프로젝트 구조(tests/eval/evalsets/, tests/eval/eval_config.json)를 기반으로 작동합니다.
agents-cli eval run 명령어 하나로 시나리오 추론(generate)과 채점(grade)을 체이닝하여 즉각적인 결과를 출력합니다.
AI 코딩 에이전트와의 밀접한 통합:
google-agents-cli-eval Skill을 통해 Antigravity, Claude Code, Gemini CLI 등 코딩 에이전트가 평가 결과를 읽고, 실패 원인을 분석하여 에이전트 프롬프트나 툴 코드를 즉시 수정하는 Eval-Fix Loop를 로컬에서 자율 수행하도록 최적화되어 있습니다.
회귀 테스트 및 결과 비교:
agents-cli eval compare를 지원하여 프롬프트/코드 수정 전후의 지표 변화와 궤적(trajectory)을 CLI 상에서 바로 대조할 수 있습니다.
(2) Agent Platform SDK (client.evals)
풀스택 품질 플라이휠 (Quality Flywheel):
SDK는 평가 전체 라이프사이클을 세분화된 API 메서드로 제공합니다:
시나리오 합성 (client.evals.generate_conversation_scenarios): 사용자 시뮬레이션을 위한 멀티턴 테스트 케이스 자동 생성.
추론 실행 (client.evals.run_inference): User Simulator 및 환경 시뮬레이션(도구 호출 Mocking 등)을 통해 실행 추적(Trace) 캡처.
자동 채점 (client.evals.evaluate): MULTI_TURN_TASK_SUCCESS, MULTI_TURN_TOOL_USE_QUALITY 등 멀티턴 전용 AutoRater 및 LLM-as-a-judge 적용.
실패 클러스터링 (client.evals.generate_loss_clusters): 평가 실패 건들을 공통 오류 패턴별로 군집화.
프롬프트 자동 최적화 (client.optimizer.optimize): 실패 분석 결과를 기반으로 에이전트의 시스템 프롬프트 등을 프로그래밍 방식으로 자동 개선.
프로덕션/대규모 환경 지원:
실제 운영 트래픽(Live production traces)에 대한 지속적 온라인 모니터링(Online Evaluation) 및 Cloud 대규모 배치 평가 파이프라인에 직접 통합할 수 있습니다.
