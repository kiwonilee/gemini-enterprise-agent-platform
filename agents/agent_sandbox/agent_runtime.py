import os
import json
from dotenv import load_dotenv

# Configuration parameters
load_dotenv(override=True)

import agentplatform
from agentplatform import types
from agentplatform.frameworks import AdkApp

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GCP_RESOURCES_LOCATION", "us-central1")
STAGING_BUCKET = os.environ.get("STAGING_BUCKET_URI")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

SERVICE_ACCOUNT = os.environ.get("SERVICE_ACCOUNT", f"sa-agent-platform@{PROJECT_ID}.iam.gserviceaccount.com")

# Initialize the Agent Platform client
print(f"Initializing Vertex AI Client (Project: {PROJECT_ID}, Location: {LOCATION})...")
client = agentplatform.Client(
    project=PROJECT_ID,
    location=LOCATION
)

sandbox_name = os.environ.get("SANDBOX_RESOURCE_NAME")
if sandbox_name:
    print(f"✅ Using existing Sandbox from environment: {sandbox_name}")
else:
    # Create top-level Agent Runtime container and a managed sandbox under it
    print("Creating top-level AgentEngine container...")
    agent_engine = client.runtimes.create()
    container_name = agent_engine.api_resource.name
    print(f"✅ Agent Runtime container created: {container_name}")

    print(f"Creating Agent Sandbox under {container_name}...")
    operation = client.sandboxes.create(
        name=container_name,
        config=types.CreateRuntimeSandboxConfig(display_name="Agent Sandbox"),
        spec={
            "code_execution_environment": {
                "code_language": "LANGUAGE_PYTHON",  # Programming language for execution
                "machine_config": "MACHINE_CONFIG_VCPU4_RAM4GIB",  # Resource settings
            }
        },
    )
    sandbox_name = operation.response.name
    print(f"✅ Sandbox created successfully! Resource name: {sandbox_name}")

# Set the environment variable BEFORE importing the agent, so that
# the AgentEngineSandboxCodeExecutor is created with the explicit sandbox resource name.
print(f"Injecting SANDBOX_RESOURCE_NAME into local environment: {sandbox_name}")
os.environ["SANDBOX_RESOURCE_NAME"] = sandbox_name

# Now import the agent cleanly
from agent import root_agent as agent

# Use the proper wrapper class for your Agent Framework
print("Wrapping agent in AdkApp...")
adk_app = AdkApp(agent=agent)

# Deploy Agent to Vertex AI Agent Runtime
print("Deploying Agent to Agent Runtime container...")
agent_runtime_config = {
    "display_name": "Agent Sandbox",
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
