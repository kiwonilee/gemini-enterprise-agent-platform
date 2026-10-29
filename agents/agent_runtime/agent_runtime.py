import os
import json
from dotenv import load_dotenv

# Configuration parameters
load_dotenv(override=True)

import agentplatform
from agentplatform.frameworks import AdkApp
from agent import root_agent as agent

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GCP_RESOURCES_LOCATION")
STAGING_BUCKET = os.environ.get("STAGING_BUCKET_URI")

print(f"🛠️ Initializing Agent Platform Client (Project: {PROJECT_ID}, Location: {LOCATION}...")
client = agentplatform.Client(
    project=PROJECT_ID,
    location=LOCATION,
    # Agent Identity 는 v1veta1 에서 지원하고 있기 때문에 명시 필요 (# https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/agent-identity#create-agent-identity)
    http_options=dict(api_version="v1beta1") 
)

# Use the proper wrapper class for your Agent Framework
adk_app = AdkApp(agent=agent)

# MemoryBank 설정 (https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/setup#memory-bank-config)
memory_bank_config = {
    # Default Model for Memory Bank is gemini-3.5-flash
    # defining the model will be used to extract and consolidate memories.
    "generation_config": {
        "model": f"projects/{PROJECT_ID}/locations/global/publishers/google/models/gemini-3.8-flash",
    },
    # Default for Similarity Search Model is text-embedding-005
    # defining the model will be used for similarity search, including during consolidation.
    # text-embedding-005 is supported only English, but gemini-embedding-2 is supported multilingual.
    "similarity_search_config": {
        "embedding_model": f"projects/{PROJECT_ID}/locations/global/publishers/google/models/gemini-embedding-2"
    },
    # Default TTL for memory revisions is 365 days.
    "ttl_config": {
        "memory_revision_default_ttl": f"{365 * 24 * 60 * 60}s"
    },     
    "customization_configs": [
        {
            "consolidation_config": {
                # Only use the latest memory revision of each candidate memory during consolidation
                "revisions_per_candidate_count": 3
            }
        }
    ],
}
print(f"🛠️ Setting the Memory Bank config:\n{json.dumps(memory_bank_config, indent=2)}")

# Create a new resource with your agent deployed to Agent Runtime.
# https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/deploy-an-agent#create-agent-platform-instance
agent_runtime_config={
    "display_name": "Agent Runtime",
    # https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/deploy-an-agent#agent-identity
    "identity_type": "AGENT_IDENTITY",
    # https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/deploy-an-agent#customized-resource-controls
    "min_instances": 1,                                 # default : 1
    "max_instances": 10,                                # default : 100    
    "resource_limits": {"cpu": "4", "memory": "4Gi"},   # default : {"cpu": "4", "memory": "4Gi"}.    
    "container_concurrency": 9,                         # recommand : (2 * cpu + 1)
    "staging_bucket": STAGING_BUCKET,
    "extra_packages": ["agent.py"],
    "requirements": [
        # See https://pypi.org/project/google-cloud-aiplatform for the latest version.
        "google-cloud-aiplatform[agent_engines,adk]",
        "google-adk",
        "cloudpickle",
        "pydantic",            
    ],
    "env_vars": {
        "GOOGLE_CLOUD_LOCATION": "global",
        "GOOGLE_GENAI_USE_VERTEXAI": "TRUE",
        # SessionService, MemoryService, ArtifactService
        "ADK_SESSION_SERVICE_URI": "agentengine://",
        "ADK_MEMORY_SERVICE_URI": "agentengine://",
        "ADK_ARTIFACT_SERVICE_URI": STAGING_BUCKET,
        # Telemetry (https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/tracing?hl=ko#write-traces)
        "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
        "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_latest_experimental",
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "EVENT_ONLY",
        # Context-Aware Access 해제 ( Agent Identity 했을 때, 401 UNAUTHENTICATED 오류 나는 경우)
        # https://docs.cloud.google.com/iam/docs/auth-agent-own-identity?hl=ko#opt-out-caa
        # https://docs.cloud.google.com/iam/docs/troubleshoot-auth-manager?hl=ko#401-error
        "GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES": "False",
    },
    "context_spec": {"memory_bank_config": memory_bank_config},
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

print("----------------------------------------------------------------------------------")
print("⚠️ Run the following commands to grant required permissions to the Agent Identity")
print("----------------------------------------------------------------------------------")
print(f'export AGENT_IDENTITY="{effective_identity}"\n')
roles = [
    "roles/aiplatform.user",
    "roles/aiplatform.viewer",    
    "roles/serviceusage.serviceUsageConsumer",
    "roles/apptopology.viewer",  # for agent relationship
    "roles/agentregistry.viewer",  # for agent relationship
    "roles/cloudtrace.user",  # for agent trace
    "roles/logging.logWriter", # for agent log
    "roles/logging.viewer",  # for agent log    
]

for role in roles:
    print(f"gcloud projects add-iam-policy-binding {PROJECT_ID} \\")
    print(f'    --member="principal://$AGENT_IDENTITY" \\')
    print(f'    --role="{role}"')
