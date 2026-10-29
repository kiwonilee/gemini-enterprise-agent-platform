import os
import json
from dotenv import load_dotenv

# Configuration parameters
load_dotenv(override=True)

import agentplatform
from agentplatform.frameworks import AdkApp
from agent import root_agent as agent

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GCP_RESOURCES_LOCATION", "us-central1")
STAGING_BUCKET = os.environ.get("STAGING_BUCKET_URI")

SERVICE_ACCOUNT = os.environ.get("SERVICE_ACCOUNT", f"sa-agent-platform@{PROJECT_ID}.iam.gserviceaccount.com")

print(f"Initializing Vertex AI Client (Project: {PROJECT_ID}, Location: {LOCATION}, Service Account: {SERVICE_ACCOUNT})...")
client = agentplatform.Client(
    project=PROJECT_ID, 
    location=LOCATION
)

# Use the proper wrapper class for your Agent Framework
adk_app = AdkApp(agent=agent)

# Create a new resource with your agent deployed to Agent Runtime.
# https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/deploy-an-agent#create-agent-platform-instance
agent_runtime_config={
    "display_name": "Agent Skills",
    "service_account" : SERVICE_ACCOUNT,
    "staging_bucket": STAGING_BUCKET,
    "extra_packages": ["agent.py"],
    "requirements": [
        "google-adk[agent-identity,a2a]>=2.2.0",
        "google-cloud-aiplatform[agent_engines]",
        "google-genai",
        "google-auth",
        "python-dotenv",
        "pydantic",
        "cloudpickle",
        "mcp>=1.27.1",
        "pyyaml>=6.0.3",
    ],
    "env_vars": {
        "GOOGLE_CLOUD_LOCATION": "global",
        "GCP_RESOURCES_LOCATION": LOCATION,
        "GOOGLE_GENAI_USE_VERTEXAI": "TRUE",
        # SessionService, MemoryService, ArtifactService
        "ADK_SESSION_SERVICE_URI": "agentengine://",
        "ADK_MEMORY_SERVICE_URI": "agentengine://",
        "ADK_ARTIFACT_SERVICE_URI": STAGING_BUCKET,
        # Telemetry (https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/tracing?hl=ko#write-traces)
        "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
        "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_latest_experimental",
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "EVENT_ONLY"
    }
}
print(f"🛠️ Setting the Agent Runtime config Bank config:\n{json.dumps(agent_runtime_config, indent=2)}")

# Create Agent Runtime (https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/deploy-an-agent#create-agent-platform-instance)
existing = next((e for e in client.runtimes.list() if e.api_resource.display_name == agent_runtime_config["display_name"]), None)
if existing:
    print(f"🚀 Existing agent found ({existing.api_resource.name}). Updating revision...")
    remote_agent = client.runtimes.update(
        name=existing.api_resource.name,
        agent=adk_app,
        config=agent_runtime_config,
    )
else:
    print("🚀 Deploying new Agent to Agent Runtime...")
    remote_agent = client.runtimes.create(
        agent=adk_app,
        config=agent_runtime_config,
    )

print("\n✅ Deployment successful!")
print(f"📌 Remote Agent Name: {remote_agent.api_resource.name}")
effective_identity = remote_agent.api_resource.spec.effective_identity
print(f"📌 Agent Identity: {effective_identity}")
