#!/usr/bin/env python3
"""Enterprise Skill Registry Administration CLI Tool.

Provides subcommands: list, create, get, delete, retrieve, and import for
managing Vertex AI Agent Platform Skill Registry.
"""

import argparse
import os
from dotenv import load_dotenv

load_dotenv(override=True)

import re
import shutil
import subprocess
import tempfile
from datetime import datetime
import yaml
import agentplatform

# -----------------------------------------------------------------------------
# Core Management Subcommand Functions
# -----------------------------------------------------------------------------

def list_skills(client):
  """Lists all registered skills in the project region."""
  print(f"\n--- Active Skills in Registry ---")
  count = 0
  for skill in client.skills.list():
    print(f"* Display Name: {skill.display_name}")
    print(f"  Resource URI: {skill.name}")
    print(f"  Description : {skill.description}")
    print("-" * 50)
    count += 1
  print(f"Total registered skills found: {count}\n")


def create_skill(client, display_name: str, description: str, local_path: str, skill_id: str = None, base_slug: str = None):
  """Registers/Creates a new skill in the registry."""
  if not skill_id:
    # Auto-generate a slug-friendly skill ID
    seed = base_slug or display_name
    clean_slug = "".join(c for c in seed.lower().replace(" ", "-").replace("_", "-") if c.isalnum() or c == "-")
    clean_slug = re.sub(r"-+", "-", clean_slug).strip("-")

    # Vertex AI Skill ID cannot start with reserved prefix 'gcp-'
    while clean_slug.startswith("gcp-"):
      clean_slug = clean_slug[4:]
    clean_slug = clean_slug.strip("-")
    if not clean_slug:
      clean_slug = "skill"

    skill_id = f"{clean_slug[:45].rstrip('-')}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

  print(f"Creating skill '{display_name}' ({skill_id}) from local path '{local_path}'...")
  created_skill = client.skills.create(
      skill_id=skill_id,
      display_name=display_name,
      description=description,
      config={"local_path": local_path}
  )
  print(f"SUCCESS: Skill registered. Resource Name: {created_skill.name}\n")
  return created_skill


def get_skill(client, skill_name_or_id: str, project_id: str, location: str):
  """Gets a single registered skill by its name/ID."""
  full_resource_name = (
      skill_name_or_id
      if skill_name_or_id.startswith("projects/")
      else f"projects/{project_id}/locations/{location}/skills/{skill_name_or_id}"
  )
  print(f"Fetching skill: {full_resource_name}...")
  skill = client.skills.get(name=full_resource_name)
  print(f"\n--- Skill Details ---")
  print(f"  Display Name: {skill.display_name}")
  print(f"  Resource URI: {skill.name}")
  print(f"  Description : {skill.description}\n")
  return skill


def delete_skill(client, skill_name_or_id: str, project_id: str, location: str):
  """Deletes a registered skill by its name/ID."""
  full_resource_name = (
      skill_name_or_id
      if skill_name_or_id.startswith("projects/")
      else f"projects/{project_id}/locations/{location}/skills/{skill_name_or_id}"
  )
  print(f"Deleting skill: {full_resource_name}...")
  client.skills.delete(name=full_resource_name)
  print(f"SUCCESS: Deleted skill '{skill_name_or_id}'\n")


def retrieve_skills(client, query: str, top_k: int = 2):
  """Performs semantic RAG search on the registered skills."""
  print(f"Querying skills matching: '{query}' (top_k={top_k})...")
  response = client.skills.retrieve(query=query, config={"top_k": top_k})
  print(f"\n--- Semantic Retrieval Results for: '{query}' ---")
  print(f"Found {len(response.retrieved_skills)} matching skills.")
  for i, retrieved in enumerate(response.retrieved_skills):
    print(f"  [{i+1}] Skill Name : {retrieved.skill_name}")
    print(f"      Description: {retrieved.description}")
    print("-" * 50)
  print()
  return response


# -----------------------------------------------------------------------------
# GitHub Skills Import Helpers
# -----------------------------------------------------------------------------

def download_github_repo(url: str, dest_dir: str):
  """Clones a public GitHub repository into the target destination folder."""
  print(f"Cloning GitHub repo '{url}'...")
  subprocess.run(["git", "clone", "--depth=1", url, dest_dir], check=True, capture_output=True)


def parse_skill_md(filepath: str, default_name: str):
  """Parses a standard SKILL.md file to dynamically extract name, display name, and description."""
  skill_slug = default_name
  display_name = default_name
  description = f"SRE playbook handbook imported from {default_name} playbook."

  if os.path.exists(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
      content = f.read().strip()

    # 1. Parse YAML frontmatter if available
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if fm_match:
      try:
        frontmatter = yaml.safe_load(fm_match.group(1))
        if isinstance(frontmatter, dict):
          if frontmatter.get("name"):
            skill_slug = str(frontmatter["name"]).strip()
          if frontmatter.get("description"):
            description = str(frontmatter["description"]).strip()
      except Exception:
        pass

    # 2. Extract first H1 header for display name
    h1_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if h1_match:
      display_name = h1_match.group(1).strip()
    elif skill_slug:
      display_name = skill_slug.replace("-", " ").title()

    # 3. Fallback description from first paragraph if not in frontmatter
    if not description or description.startswith("SRE playbook handbook"):
      body = content[fm_match.end():] if fm_match else content
      paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
      for p in paragraphs:
        if not p.startswith("#") and len(p) > 15:
          description = re.sub(r"\s+", " ", p)
          break

  if len(description) > 300:
    description = description[:297] + "..."
  return skill_slug, display_name, description


def import_skills_from_github(client, repo_url: str, sub_path: str = None):
  """Clones a GitHub repo, automatically scans SRE playbooks containing SKILL.md, and registers them."""
  output_dir = tempfile.mkdtemp()
  try:
    download_github_repo(repo_url, output_dir)
    search_path = os.path.join(output_dir, sub_path.lstrip("/")) if sub_path else output_dir

    print(f"Scanning for SRE playbooks under: '{search_path}'...")
    skills_found = []

    for root, _, files in os.walk(search_path):
      if ".git" in root:
        continue
      if "SKILL.md" in files:
        skill_slug, display_name, description = parse_skill_md(os.path.join(root, "SKILL.md"), os.path.basename(root))
        skills_found.append({"skill_slug": skill_slug, "display_name": display_name, "description": description, "local_path": root})

    if not skills_found:
      print(f"No playbook directories containing 'SKILL.md' found.")
      return

    print(f"\n--- Detected {len(skills_found)} Playbooks for Import ---")

    # Fetch already registered skills to avoid duplicate registration
    print("Checking already registered skills in Skill Registry...")
    existing_skills = {}
    try:
      for reg_skill in client.skills.list():
        existing_skills[reg_skill.display_name.lower().strip()] = reg_skill.name
        short_id = reg_skill.name.split("/")[-1]
        existing_skills[short_id.lower().strip()] = reg_skill.name
      print(f"Found {len(existing_skills)} existing skills/identifiers in registry.")
    except Exception as e:
      print(f"⚠️ Warning: Could not list existing skills ({e}). Will proceed with creation.")

    skipped_count = 0
    success_count = 0
    failed_skills = []

    for s in skills_found:
      d_name = s["display_name"]
      slug = s["skill_slug"]

      # Check if already registered by display_name or slug
      if d_name.lower().strip() in existing_skills or slug.lower().strip() in existing_skills:
        print(f"⏭️  SKIP: Skill '{d_name}' is already registered in registry. Passing...")
        skipped_count += 1
        continue

      try:
        create_skill(client, d_name, s["description"], s["local_path"], base_slug=slug)
        success_count += 1
      except Exception as e:
        print(f"❌ FAILED to register skill '{d_name}' ({slug}): {e}")
        print("   Skipping to the next skill...\n")
        failed_skills.append((d_name, str(e)))

    print("\n" + "=" * 50)
    print("📊 Import Summary:")
    print(f"  - Total detected     : {len(skills_found)}")
    print(f"  - Already registered : {skipped_count} (Passed)")
    print(f"  - Newly registered   : {success_count} (Success)")
    print(f"  - Failed             : {len(failed_skills)}")

    if failed_skills:
      print("\n⚠️ Failed Skills Details:")
      for name, err in failed_skills:
        print(f"  * {name}: {err}")
    print("=" * 50 + "\n")

  finally:
    print(f"Cleaning up temporary folder '{output_dir}'...")
    shutil.rmtree(output_dir, ignore_errors=True)


# -----------------------------------------------------------------------------
# Main CLI Entry Point
# -----------------------------------------------------------------------------

def main():
  # 1. Load .env before configuring argument parser
  load_dotenv(override=True)

  parser = argparse.ArgumentParser(description="Vertex AI Agent Platform Skill Registry CLI")
  parser.add_argument("--project-id", default=os.environ.get("GOOGLE_CLOUD_PROJECT"))
  parser.add_argument("--location", default=os.environ.get("GCP_RESOURCES_LOCATION", "us-central1"))

  subparsers = parser.add_subparsers(dest="command", required=True)

  # Subcommands
  subparsers.add_parser("list", help="List registered skills")

  create_parser = subparsers.add_parser("create", help="Register a new skill from local playbook path")
  create_parser.add_argument("--display-name", required=True)
  create_parser.add_argument("--description", required=True)
  create_parser.add_argument("--local-path", required=True)
  create_parser.add_argument("--skill-id", default=None)

  get_parser = subparsers.add_parser("get", help="Retrieve detailed specs of a registered skill")
  get_parser.add_argument("--skill-name", required=True)

  delete_parser = subparsers.add_parser("delete", help="Delete a registered skill")
  delete_parser.add_argument("--skill-name", required=True)

  retrieve_parser = subparsers.add_parser("retrieve", help="Perform RAG semantic search query")
  retrieve_parser.add_argument("--query", required=True)
  retrieve_parser.add_argument("--top-k", type=int, default=2)

  import_parser = subparsers.add_parser("import", help="Import SRE playbooks from a public GitHub repository")
  import_parser.add_argument("--github-url", required=True)
  import_parser.add_argument("--sub-path", default=None)

  args = parser.parse_args()

  # Initialize Agent Platform client using resolved arguments
  print(f"🛠️ Initializing Agent Platform Client (Project: {args.project_id}, Location: {args.location})...")
  client = agentplatform.Client(
    project=args.project_id,
    location=args.location,
  )

  try:
    if args.command == "list":
      list_skills(client)
    elif args.command == "create":
      create_skill(client, args.display_name, args.description, args.local_path, args.skill_id)
    elif args.command == "get":
      get_skill(client, args.skill_name, args.project_id, args.location)
    elif args.command == "delete":
      delete_skill(client, args.skill_name, args.project_id, args.location)
    elif args.command == "retrieve":
      retrieve_skills(client, args.query, args.top_k)
    elif args.command == "import":
      import_skills_from_github(client, args.github_url, args.sub_path)
  except Exception as e:
    print(f"\nERROR: Execution failed: {e}")


if __name__ == "__main__":
  main()