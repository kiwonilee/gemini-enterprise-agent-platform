# 로컬 환경 세팅 - 노트북 실행에 사용할 Python 환경과 커널 패키지를 설치

```bash
# 1. 프로젝트 폴더로 이동 (루트에서 uv sync를 실행했다면 루트 .venv 커널을 바로 사용할 수 있습니다)
cd ~/workspace/gemini-enterprise-agent-platform/notebooks/agent-runtime

# 2. uv로 가상환경 생성 (--seed 옵션을 추가해야 노트북 내에서 %pip 명령어가 동작합니다)
uv venv --seed .venv

# 3. ipykernel 및 Agent Platform 개발/평가에 필요한 라이브러리 일괄 설치
# (Google 사내 환경에서는 airlock-proxy 인덱스 지정 필요)
uv pip install \
  --index-url http://airlock-proxy.uplink.goog:999/python/artifact-foundry-prod/ah-3p-staging-python/simple/ \
  --allow-insecure-host airlock-proxy.uplink.goog \
  pip ipykernel numpy pandas matplotlib cloudpickle pydantic \
  "google-cloud-aiplatform[adk,agent_engines]"
```