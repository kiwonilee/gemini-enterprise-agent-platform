#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/cleanup_all.sh [options] [agent-name...]

Options:
  --dry-run          삭제 대상(Reasoning Engine, Sandbox, IAM 바인딩, Service Account)만 조회하고 실제 삭제는 수행하지 않음
  --skip-sa          Reasoning Engine만 삭제하고 서비스 계정(SA)은 유지
  --include-bucket   Staging GCS 버킷(STAGING_BUCKET_URI)까지 함께 삭제
  -y, --yes          확인 프롬프트 없이 즉시 삭제 실행
  -h, --help         도움말 출력

Examples:
  ./scripts/cleanup_all.sh --dry-run              # 삭제 대상 미리보기
  ./scripts/cleanup_all.sh                        # 전체 Reasoning Engine + Sandbox + SA + IAM 정리
  ./scripts/cleanup_all.sh -y                     # 확인 없이 전체 즉시 정리
  ./scripts/cleanup_all.sh agent-sandbox          # 특정 에이전트(및 연결된 SA/Sandbox)만 정리
EOF
}

DRY_RUN="false"
SKIP_SA="false"
INCLUDE_BUCKET="false"
AUTO_YES="false"
TARGET_AGENTS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN="true"
      shift
      ;;
    --skip-sa)
      SKIP_SA="true"
      shift
      ;;
    --include-bucket)
      INCLUDE_BUCKET="true"
      shift
      ;;
    -y|--yes)
      AUTO_YES="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      TARGET_AGENTS+=("$1")
      shift
      ;;
  esac
done

export DRY_RUN SKIP_SA INCLUDE_BUCKET AUTO_YES

uv run python - "${TARGET_AGENTS[@]}" <<'PY'
import json
import os
import re
import subprocess
import sys
from pathlib import Path
import requests
from dotenv import load_dotenv

ROOT_DIR = Path.cwd()
ENV_FILE = ROOT_DIR / ".env"
load_dotenv(ENV_FILE, override=True)

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") or subprocess.check_output(
    ["gcloud", "config", "get-value", "project"]
).decode().strip()
LOCATION = os.environ.get("GCP_RESOURCES_LOCATION", "us-central1")
STAGING_BUCKET_URI = os.environ.get("STAGING_BUCKET_URI", "")

DRY_RUN = os.environ.get("DRY_RUN") == "true"
SKIP_SA = os.environ.get("SKIP_SA") == "true"
INCLUDE_BUCKET = os.environ.get("INCLUDE_BUCKET") == "true"
AUTO_YES = os.environ.get("AUTO_YES") == "true"

AGENTS = {
    "agent_runtime": {
        "display_name": "Agent Runtime",
        "sa_name": None,  # Uses AGENT_IDENTITY
        "identity_roles": [
            "roles/aiplatform.user",
            "roles/aiplatform.viewer",
            "roles/serviceusage.serviceUsageConsumer",
            "roles/apptopology.viewer",
            "roles/agentregistry.viewer",
            "roles/cloudtrace.user",
            "roles/logging.logWriter",
            "roles/logging.viewer",
        ],
    },
    "agent_registry_mcp": {
        "display_name": "Agent Registry for MCP",
        "sa_name": "sa-agent-registry",
        "sa_roles": [
            "roles/cloudtrace.user",
            "roles/cloudtrace.agent",
            "roles/logging.viewer",
            "roles/logging.logWriter",
            "roles/storage.objectAdmin",
            "roles/aiplatform.user",
            "roles/agentregistry.viewer",
            "roles/mcp.toolUser",
        ],
    },
    "agent_sandbox": {
        "display_name": "Agent Sandbox",
        "sa_name": "sa-agent-sandbox",
        "sa_roles": [
            "roles/cloudtrace.user",
            "roles/cloudtrace.agent",
            "roles/logging.viewer",
            "roles/logging.logWriter",
            "roles/storage.objectAdmin",
            "roles/aiplatform.user",
        ],
    },
    "agent_skills": {
        "display_name": "Agent Skills",
        "sa_name": "sa-skill-registry",
        "sa_roles": [
            "roles/cloudtrace.user",
            "roles/cloudtrace.agent",
            "roles/logging.viewer",
            "roles/logging.logWriter",
            "roles/aiplatform.user",
            "roles/serviceusage.serviceUsageConsumer",
            "roles/agentregistry.viewer",
        ],
    },
    "graph_workflow": {
        "display_name": "Graph Workflow",
        "sa_name": "sa-graph-workflow",
        "sa_roles": [
            "roles/cloudtrace.user",
            "roles/cloudtrace.agent",
            "roles/logging.viewer",
            "roles/logging.logWriter",
            "roles/aiplatform.user",
        ],
    },
}

args = [a.replace("-", "_") for a in sys.argv[1:]]
if args:
    for a in args:
        if a not in AGENTS:
            print(f"❌ 알 수 없는 에이전트 이름입니다: {a} (선택 가능: {', '.join(AGENTS.keys())})")
            sys.exit(1)
    target_keys = args
    is_full_cleanup = False
else:
    target_keys = list(AGENTS.keys())
    is_full_cleanup = True

token = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
base_api = f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1"

print("======================================================================")
print(f"🔎 조회 중인 프로젝트: {PROJECT_ID} (리전: {LOCATION})")
if DRY_RUN:
    print("💡 [DRY-RUN 모드] 실제 삭제를 수행하지 않고 대상 리소스만 출력합니다.")
print("======================================================================")

resp = requests.get(
    f"{base_api}/projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines",
    headers=headers,
    timeout=60,
)
resp.raise_for_status()
all_engines = resp.json().get("reasoningEngines", [])

target_display_names = {AGENTS[k]["display_name"]: k for k in target_keys}
engines_to_delete = []
identities_to_cleanup = []

sandbox_env_res = os.environ.get("SANDBOX_RESOURCE_NAME", "")
sandbox_parent_engine = None
if "agent_sandbox" in target_keys and "/sandboxEnvironments/" in sandbox_env_res:
    sandbox_parent_engine = sandbox_env_res.split("/sandboxEnvironments/")[0]

for eng in all_engines:
    name = eng.get("name", "")
    dname = eng.get("displayName", "")
    eff_id = eng.get("spec", {}).get("effectiveIdentity", "")

    if dname in target_display_names:
        agent_key = target_display_names[dname]
        engines_to_delete.append((agent_key, dname, name))
        if agent_key == "agent_runtime" and eff_id:
            identities_to_cleanup.append((eff_id, AGENTS["agent_runtime"]["identity_roles"]))
    elif sandbox_parent_engine and name.endswith(sandbox_parent_engine.split("/")[-1]):
        engines_to_delete.append(("agent_sandbox (Sandbox Container)", "<Sandbox Container>", name))
    elif is_full_cleanup and not dname:
        # Check if unnamed engine hosts sandboxEnvironments
        sb_resp = requests.get(f"{base_api}/{name}/sandboxEnvironments", headers=headers, timeout=30)
        if sb_resp.ok and sb_resp.json().get("sandboxEnvironments"):
            engines_to_delete.append(("agent_sandbox (Sandbox Container)", "<Sandbox Container>", name))

sas_to_delete = []
if not SKIP_SA:
    for k in target_keys:
        sa_name = AGENTS[k]["sa_name"]
        if not sa_name:
            continue
        sa_email = f"{sa_name}@{PROJECT_ID}.iam.gserviceaccount.com"
        check = subprocess.run(
            ["gcloud", "iam", "service-accounts", "describe", sa_email, f"--project={PROJECT_ID}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if check.returncode == 0:
            sas_to_delete.append((k, sa_email, AGENTS[k]["sa_roles"]))

print("\n📋 [정리 대상 요약]")
print(f"  1) Reasoning Engines ({len(engines_to_delete)}개):")
if engines_to_delete:
    for key, dname, rname in engines_to_delete:
        print(f"     - [{key}] {dname}: {rname} (force=true 포함 하위 세션/메모리/샌드박스 일괄 삭제)")
else:
    print("     - (없음)")

print(f"  2) Agent Identity IAM 바인딩 ({len(identities_to_cleanup)}개):")
if identities_to_cleanup:
    for eff_id, roles in identities_to_cleanup:
        print(f"     - principal://{eff_id} ({len(roles)}개 역할)")
else:
    print("     - (없음)")

print(f"  3) Service Accounts 및 IAM 바인딩 ({len(sas_to_delete)}개):")
if SKIP_SA:
    print("     - (--skip-sa 옵션으로 건너뜀)")
elif sas_to_delete:
    for key, sa_email, roles in sas_to_delete:
        print(f"     - [{key}] {sa_email} (IAM 역할 {len(roles)}개 해제 후 계정 삭제)")
else:
    print("     - (없음)")

if INCLUDE_BUCKET and STAGING_BUCKET_URI:
    print(f"  4) GCS Staging Bucket: {STAGING_BUCKET_URI}")

if DRY_RUN:
    print("\n✅ Dry-run 완료. 실제 삭제하려면 --dry-run 옵션을 제거하고 실행하세요.")
    sys.exit(0)

if not engines_to_delete and not sas_to_delete and not (INCLUDE_BUCKET and STAGING_BUCKET_URI):
    print("\n✅ 정리할 리소스가 없습니다.")
    sys.exit(0)

if not AUTO_YES:
    ans = input("\n⚠️ 위 리소스를 영구 삭제하시겠습니까? [y/N]: ").strip().lower()
    if ans not in ("y", "yes"):
        print("🛑 사용자가 취소했습니다.")
        sys.exit(0)

print("\n🚀 리소스 정리를 시작합니다...")

# 1. Delete Reasoning Engines (with force=true)
for key, dname, rname in engines_to_delete:
    print(f"🗑️  Deleting Reasoning Engine [{key}] ({rname})...")
    del_resp = requests.delete(f"{base_api}/{rname}", params={"force": "true"}, headers=headers, timeout=120)
    if del_resp.ok:
        print(f"   ✅ 삭제 요청 완료 ({rname})")
    else:
        print(f"   ⚠️ 삭제 실패 ({del_resp.status_code}): {del_resp.text}")

# Clean SANDBOX_RESOURCE_NAME in .env if agent_sandbox was deleted
if "agent_sandbox" in target_keys and ENV_FILE.exists():
    content = ENV_FILE.read_text(encoding="utf-8")
    new_content = re.sub(r'^SANDBOX_RESOURCE_NAME=.*\n?', '', content, flags=re.MULTILINE)
    if new_content != content:
        ENV_FILE.write_text(new_content, encoding="utf-8")
        print("   🧹 루트 .env에서 SANDBOX_RESOURCE_NAME 항목을 정리했습니다.")

# 2. Remove Agent Identity IAM bindings
for eff_id, roles in identities_to_cleanup:
    member = f"principal://{eff_id}"
    print(f"🔓 Removing IAM bindings for {member}...")
    for role in roles:
        subprocess.run(
            [
                "gcloud", "projects", "remove-iam-policy-binding", PROJECT_ID,
                f"--member={member}", f"--role={role}", "--quiet",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

# 3. Remove Service Account IAM bindings & Delete Service Accounts
for key, sa_email, roles in sas_to_delete:
    member = f"serviceAccount:{sa_email}"
    print(f"🔓 Removing IAM bindings for {sa_email}...")
    for role in roles:
        subprocess.run(
            [
                "gcloud", "projects", "remove-iam-policy-binding", PROJECT_ID,
                f"--member={member}", f"--role={role}", "--quiet",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    print(f"🗑️  Deleting Service Account: {sa_email}...")
    subprocess.run(
        ["gcloud", "iam", "service-accounts", "delete", sa_email, f"--project={PROJECT_ID}", "--quiet"],
        check=False,
    )
    print(f"   ✅ 삭제 완료: {sa_email}")

# 4. Optional: Delete GCS Staging Bucket
if INCLUDE_BUCKET and STAGING_BUCKET_URI:
    print(f"🗑️  Deleting GCS Bucket: {STAGING_BUCKET_URI}...")
    subprocess.run(
        ["gcloud", "storage", "rm", "--recursive", STAGING_BUCKET_URI, f"--project={PROJECT_ID}"],
        check=False,
    )

print("\n✅ 모든 지정 리소스 정리가 완료되었습니다!")
PY
