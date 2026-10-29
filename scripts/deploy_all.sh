#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

ALL_AGENTS=(
  "agent_runtime"
  "agent_registry_mcp"
  "agent_sandbox"
  "agent_skills"
  "graph_workflow"
)

if [[ $# -gt 0 ]]; then
  TARGET_AGENTS=()
  for arg in "$@"; do
    TARGET_AGENTS+=("${arg//-/_}")
  done
else
  TARGET_AGENTS=("${ALL_AGENTS[@]}")
fi

echo "=================================================================="
echo "🚀 Deploying Agents Sequentially (avoids GCS staging collisions)"
echo "=================================================================="

for agent in "${TARGET_AGENTS[@]}"; do
  agent_dir="${ROOT_DIR}/agents/${agent}"
  if [[ ! -f "${agent_dir}/agent_runtime.py" ]]; then
    echo "❌ Unknown agent or missing script: ${agent_dir}/agent_runtime.py"
    exit 1
  fi
  echo ""
  echo "------------------------------------------------------------------"
  echo "📦 Deploying [${agent}]..."
  echo "------------------------------------------------------------------"
  (cd "${agent_dir}" && uv run python agent_runtime.py)
done

echo ""
echo "=================================================================="
echo "✅ Deployment Complete! Current Active Reasoning Engines:"
echo "=================================================================="
uv run python - <<'PY'
import os
from dotenv import load_dotenv
import agentplatform

load_dotenv(".env", override=True)
project = os.environ.get("GOOGLE_CLOUD_PROJECT")
location = os.environ.get("GCP_RESOURCES_LOCATION", "us-central1")
client = agentplatform.Client(project=project, location=location)

name_map = {
    "Agent Runtime": "AGENT_RUNTIME_ID",
    "Agent Registry for MCP": "AGENT_REGISTRY_MCP_ID",
    "Agent Sandbox": "AGENT_SANDBOX_ID",
    "Agent Skills": "AGENT_SKILLS_ID",
    "Graph Workflow": "GRAPH_WORKFLOW_ID",
}

found = {}
for engine in client.runtimes.list():
    dname = engine.api_resource.display_name
    if dname in name_map and dname not in found:
        rid = engine.api_resource.name.split("/")[-1]
        found[dname] = rid
        print(f"# {dname}: {engine.api_resource.name}")
        print(f"export {name_map[dname]}=\"{rid}\"")
PY
