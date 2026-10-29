#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

uv run python - "$@" <<'PY'
import json
import os
import subprocess
import sys
from pathlib import Path
import requests
from dotenv import load_dotenv
import agentplatform

load_dotenv(".env", override=True)

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GCP_RESOURCES_LOCATION", "us-central1")

AGENTS = {
    "agent_runtime": {
        "display_name": "Agent Runtime",
        "env_var": "AGENT_RUNTIME_ID",
        "prompt": "뉴욕의 현재 날씨와 현재 시간을 알려줘.",
    },
    "agent_registry_mcp": {
        "display_name": "Agent Registry for MCP",
        "env_var": "AGENT_REGISTRY_MCP_ID",
        "prompt": f"현재 project 는 {PROJECT_ID} 이다. 최근 발생한 에러로그 5개를 분석해줘.",
    },
    "agent_sandbox": {
        "display_name": "Agent Sandbox",
        "env_var": "AGENT_SANDBOX_ID",
        "prompt": "1부터 100까지의 숫자 중 소수(Prime Number)의 개수를 구하는 파이썬 코드를 작성하고 실행 결과를 알려줘.",
    },
    "agent_skills": {
        "display_name": "Agent Skills",
        "env_var": "AGENT_SKILLS_ID",
        "prompt": "GKE 의 Cluster Upgrade 에 대한 Best Practice 에 대해서 알려줘",
    },
    "graph_workflow": {
        "display_name": "Graph Workflow",
        "env_var": "GRAPH_WORKFLOW_ID",
        "script": "agents/graph_workflow/test_workflow.py",
    },
}

args = [a.replace("-", "_") for a in sys.argv[1:]]
override_id = None
if len(args) == 0:
    target_keys = list(AGENTS.keys())
elif len(args) == 1:
    if args[0] in AGENTS:
        target_keys = [args[0]]
    else:
        print(f"❌ Unknown agent '{args[0]}'. Choose from: {', '.join(AGENTS.keys())}")
        sys.exit(1)
elif len(args) == 2:
    override_id = args[0]
    if args[1] not in AGENTS:
        print(f"❌ Unknown agent '{args[1]}'. Choose from: {', '.join(AGENTS.keys())}")
        sys.exit(1)
    target_keys = [args[1]]
else:
    print("Usage: ./scripts/test_all.sh [agent-name] OR ./scripts/test_all.sh <REASONING_ENGINE_ID> <agent-name>")
    sys.exit(1)

print(f"🔎 Discovering deployed Reasoning Engines in {PROJECT_ID} ({LOCATION})...")
client = agentplatform.Client(project=PROJECT_ID, location=LOCATION)
engine_by_display = {}
for engine in client.runtimes.list():
    dname = engine.api_resource.display_name
    if dname and dname not in engine_by_display:
        engine_by_display[dname] = engine.api_resource.name.split("/")[-1]

token = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
project_number = subprocess.check_output(
    ["gcloud", "projects", "describe", PROJECT_ID, "--format=value(projectNumber)"]
).decode().strip()
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

results = {}

for key in target_keys:
    spec = AGENTS[key]
    rid = override_id or os.environ.get(spec["env_var"]) or engine_by_display.get(spec["display_name"])
    print("\n" + "=" * 70)
    print(f"🧪 Testing [{key}] (Display Name: {spec['display_name']}, ID: {rid})")
    print("=" * 70)
    if not rid:
        print(f"❌ Could not find deployed Reasoning Engine for {key}")
        results[key] = "FAIL (Not Found)"
        continue

    if "script" in spec:
        env = os.environ.copy()
        env["REASONING_ENGINE_ID"] = rid
        cmd = [sys.executable, spec["script"]]
        proc = subprocess.run(cmd, env=env)
        results[key] = "PASS" if proc.returncode == 0 else f"FAIL (Exit {proc.returncode})"
        continue

    base_url = f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1/projects/{project_number}/locations/{LOCATION}/reasoningEngines/{rid}"
    sess_resp = requests.post(
        f"{base_url}:query",
        headers=headers,
        json={"class_method": "create_session", "input": {"user_id": "test_user"}},
        timeout=60,
    )
    sess_resp.raise_for_status()
    session_id = sess_resp.json()["output"]["id"]
    print(f"✅ Created Session ID: {session_id}")
    print(f"💬 Prompt: {spec['prompt']}")

    stream_resp = requests.post(
        f"{base_url}:streamQuery",
        headers=headers,
        json={
            "class_method": "async_stream_query",
            "input": {
                "user_id": "test_user",
                "session_id": session_id,
                "message": spec["prompt"],
            },
        },
        stream=True,
        timeout=180,
    )
    stream_resp.raise_for_status()

    final_texts = []
    tool_calls = []
    for line in stream_resp.iter_lines():
        if not line:
            continue
        decoded = line.decode("utf-8").strip()
        if decoded.startswith("data:"):
            decoded = decoded[5:].strip()
        try:
            ev = json.loads(decoded)
            for part in ev.get("content", {}).get("parts", []):
                if "function_call" in part:
                    tool_calls.append(part["function_call"].get("name"))
                if "executable_code" in part:
                    tool_calls.append("sandbox_code_execution")
                if "text" in part and part["text"].strip():
                    final_texts.append(part["text"].strip())
        except Exception:
            pass

    print(f"🔧 Invoked Tools/Actions: {tool_calls}")
    if final_texts:
        preview = final_texts[-1][:300].replace("\n", " ")
        print(f"📝 Final Response Preview: {preview}...")
        results[key] = "PASS"
    else:
        print("❌ No final text response received.")
        results[key] = "FAIL (Empty Response)"

print("\n" + "=" * 70)
print("📊 E2E Test Summary")
print("=" * 70)
all_passed = True
for k, status in results.items():
    icon = "✅" if status == "PASS" else "❌"
    print(f"  {icon} {k:22s}: {status}")
    if status != "PASS":
        all_passed = False

if not all_passed:
    sys.exit(1)
PY
