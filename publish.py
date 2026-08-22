#!/usr/bin/env python3
"""Publish the verified draft once, then set its image without changing the slug."""

import json
import pathlib
import sys

SKILL = pathlib.Path("/Users/haseeb/.pi/agent/skills/create-template-for-railway/scripts")
sys.path.insert(0, str(SKILL))
import rw  # pyright: ignore[reportMissingImports]

ROOT = pathlib.Path(__file__).parent
WORKSPACE = "fc4796db-2c6c-4354-a564-d4a1d900af53"
NAME = "OpenReply"
CATEGORY = "Automation"
DESCRIPTION = "Instagram comment-to-DM automation with Postgres, Redis, and a worker"
ICON = "https://raw.githubusercontent.com/diwenne/openreply/80fa38780e2973a0299c05019bc0d0657044220c/public/icon-512.png"

if len(DESCRIPTION) > 75:
    raise RuntimeError(f"description has {len(DESCRIPTION)} characters")
template = json.loads((ROOT / ".state" / "template.json").read_text())
listing = (ROOT / "TEMPLATE_OVERVIEW.md").read_text()
published = rw.gql(
    """mutation($id:String!,$input:TemplatePublishInput!){
         templatePublish(id:$id,input:$input){ id code name isApproved }
       }""",
    {
        "id": template["id"],
        "input": {
            "category": CATEGORY,
            "description": DESCRIPTION,
            "readme": listing,
            "workspaceId": WORKSPACE,
        },
    },
)["templatePublish"]
rw.gql(
    """mutation($id:String!,$input:TemplateUpsertSettingsInput!){
         templateUpsertSettings(id:$id,input:$input){ id code image }
       }""",
    {
        "id": template["id"],
        "input": {
            "workspaceId": WORKSPACE,
            "name": NAME,
            "image": ICON,
            "description": DESCRIPTION,
        },
    },
    internal=True,
)
state = ROOT / ".state" / "published.json"
state.write_text(json.dumps(published, indent=2) + "\n")
print(json.dumps(published, indent=2))
print(f"https://railway.com/deploy/{published['code']}")
