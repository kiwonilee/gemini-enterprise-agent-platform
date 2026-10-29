import os
import json
import time
from dotenv import load_dotenv

# Configuration parameters
load_dotenv(override=True)

import agentplatform
from agentplatform import types
from agentplatform.frameworks import AdkApp
from google.genai import errors as genai_errors

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GCP_RESOURCES_LOCATION", "us-central1")
STAGING_BUCKET = os.environ.get("STAGING_BUCKET_URI")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
DISPLAY_NAME = "Agent Sandbox"

SERVICE_ACCOUNT = os.environ.get("SERVICE_ACCOUNT", f"sa-agent-platform@{PROJECT_ID}.iam.gserviceaccount.com")

# Initialize the Agent Platform client
print(f"Initializing Agent Platform Client (Project: {PROJECT_ID}, Location: {LOCATION})...")
client = agentplatform.Client(
    project=PROJECT_ID,
    location=LOCATION,
)

# 1. Find or create the top-level Agent Runtime container (with display_name="Agent Sandbox")
existing = next(
    (e for e in client.runtimes.list() if e.api_resource.display_name == DISPLAY_NAME),
    None,
)
if existing:
    container_name = existing.api_resource.name
    print(f"✅ Found existing Agent Runtime container: {container_name}")
else:
    print(f"Creating top-level Agent Runtime container ({DISPLAY_NAME})...")
    agent_engine = client.runtimes.create(config={"display_name": DISPLAY_NAME})
    container_name = agent_engine.api_resource.name
    print(f"✅ Agent Runtime container created: {container_name}")
    time.sleep(5)

# 2. Reuse existing sandbox or create a new one under container_name (with 503 retry for new projects)
sandbox_name = os.environ.get("SANDBOX_RESOURCE_NAME")
if not sandbox_name:
    existing_sandboxes = [
        sb for sb in client.sandboxes.list(name=container_name)
        if getattr(sb, "state", None) != "STATE_DELETING"
    ]
    if existing_sandboxes:
        sandbox_name = existing_sandboxes[0].name
        print(f"✅ Found existing Sandbox under container: {sandbox_name}")

if sandbox_name:
    print(f"✅ Using Sandbox: {sandbox_name}")
else:
    print(f"Creating Agent Sandbox under {container_name}...")
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            operation = client.sandboxes.create(
                name=container_name,
                config=types.CreateRuntimeSandboxConfig(display_name=DISPLAY_NAME),
                spec={
                    "code_execution_environment": {
                        "code_language": "LANGUAGE_PYTHON",
                        "machine_config": "MACHINE_CONFIG_VCPU4_RAM4GIB",
                    }
                },
            )
            sandbox_name = operation.response.name
            print(f"✅ Sandbox created successfully! Resource name: {sandbox_name}")
            break
        except genai_errors.ServerError as err:
            if attempt < max_attempts:
                wait_sec = 10 * attempt
                print(
                    f"⚠️ Sandbox creation returned {err.code} ({err.status}). "
                    f"Waiting {wait_sec}s before retry ({attempt}/{max_attempts})..."
                )
                time.sleep(wait_sec)
            else:
                raise

# Set the environment variable BEFORE importing the agent, so that
# the AgentEngineSandboxCodeExecutor is created with the explicit sandbox resource name.
print(f"Injecting SANDBOX_RESOURCE_NAME into local environment: {sandbox_name}")
os.environ["SANDBOX_RESOURCE_NAME"] = sandbox_name

# Now import the agent cleanly
from agent import root_agent as agent

# Use the proper wrapper class for your Agent Framework
adk_app = AdkApp(agent=agent)

# 3. Deploy Agent to the same Agent Runtime container
agent_runtime_config = {
    "display_name": DISPLAY_NAME,
    "service_account": SERVICE_ACCOUNT,
    "requirements": [
        "google-adk>=2.2.0",
        "google-cloud-aiplatform[adk,agent_engines]>=1.157.0",
        "pydantic",
        "cloudpickle>=3.0.0",
    ],
    "staging_bucket": STAGING_BUCKET,
    "extra_packages": ["agent.py"],
    "env_vars": {
        "GOOGLE_CLOUD_LOCATION": "global",
        "GOOGLE_GENAI_USE_VERTEXAI": "TRUE",
        "GEMINI_MODEL": GEMINI_MODEL,
        # SessionService, MemoryService, ArtifactService
        "ADK_SESSION_SERVICE_URI": "agentengine://",
        "ADK_MEMORY_SERVICE_URI": "agentengine://",
        "ADK_ARTIFACT_SERVICE_URI": STAGING_BUCKET,
        # Telemetry (https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/tracing?hl=ko#write-traces)
        "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
        "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_latest_experimental",
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "EVENT_ONLY",
        # Sandbox configuration injection
        "SANDBOX_RESOURCE_NAME": sandbox_name,
    },
}
print(f"🛠️ Setting the Agent Runtime config:\n{json.dumps(agent_runtime_config, indent=2)}")

print(f"🚀 Updating Agent Runtime ({container_name}) with agent code...")
remote_agent = client.runtimes.update(
    name=container_name,
    agent=adk_app,
    config=agent_runtime_config,
)

print("\n✅ Deployment successful!")
print(f"📌 Remote Agent Name: {remote_agent.api_resource.name}")
print(f"📌 Sandbox Resource Name: {sandbox_name}")
