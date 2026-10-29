# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import re
from dotenv import load_dotenv

from google.adk.integrations.skill_registry import GCPSkillRegistry

from google.adk.agents.llm_agent import Agent
from google.adk.tools.skill_toolset import SkillToolset

# Load environment variables from .env
load_dotenv(override=True)
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")


class KeywordGCPSkillRegistry(GCPSkillRegistry):
    """GCPSkillRegistry subclass that uses KEYWORD search_type with OR fallback."""

    async def _make_request(
        self,
        client,
        url: str,
        params=None,
        *,
        method: str = "GET",
        json=None,
    ):
        if (
            url.endswith("/skills:search")
            and isinstance(json, dict)
            and "search_type" not in json
        ):
            json = {**json, "search_type": "KEYWORD"}
        return await super()._make_request(
            client, url, params=params, method=method, json=json
        )

    async def search_skills(self, *, query: str):
        results = await super().search_skills(query=query)
        if not results:
            words = [
                w for w in re.findall(r"[A-Za-z0-9_-]+", query) if len(w) > 1
            ]
            if len(words) > 1:
                or_query = " OR ".join(words)
                candidates = await super().search_skills(query=or_query)
                lower_words = [w.lower() for w in words]
                candidates.sort(
                    key=lambda r: sum(
                        1
                        for w in lower_words
                        if w in f"{r.name} {r.description}".lower()
                    ),
                    reverse=True,
                )
                results = candidates[:10]
        return results

    async def get_skill(self, *, name: str):
        try:
            return await super().get_skill(name=name)
        except Exception:
            if not name.startswith("cloud.google.com-"):
                return await super().get_skill(name=f"cloud.google.com-{name}")
            raise


# Initialize the GCP Skill Registry
# https://adk.dev/integrations/skills-registry/#use-with-agent
registry = KeywordGCPSkillRegistry(
    project_id=PROJECT_ID,
    location=LOCATION,
)

# Create the SkillToolset with the Registry, You can optionally pre-load some local skills as well.
skill_toolset = SkillToolset(skills=[], registry=registry)

root_agent = Agent(
    name="agent_by_skills",
    model=GEMINI_MODEL,
    instruction="""
        You are a specialized AI agent designed to discover and execute skills registered in the **Skill Registry** to resolve user requests.

        ## Core Execution Rules

        1. **Prioritize Skill Discovery**
           - Upon receiving a user request, you must first use the `skill_toolset` tool to search for the most appropriate skill in the Skill Registry.

        2. **Skill-Grounded Execution & Source Attribution**
           - If an appropriate skill is found in the search results, strictly follow its guidance and contents to fulfill the request.
           - ⚠️ **MANDATORY**: You MUST explicitly state the **exact name of the skill** used in your final response.

        3. **Handling Missing Skills (Immediate Termination)**
           - If no suitable skill is found in the search results, do NOT make assumptions, guess, or attempt to perform any further actions.
           - Immediately respond in Korean: "요청하신 작업을 수행할 수 있는 적절한 스킬(플레이북)을 스킬 레지스트리에서 찾을 수 없습니다." and terminate the conversation.

        4. **Communication Guidelines**
           - All user interactions and final responses must be written in polite and professional Korean.
        """,
    # 3. Define your Agent with the SkillToolset/
    tools=[skill_toolset],
)
