#!/usr/bin/env python3
"""Deploy the draft into a new project exactly like Railway's deploy button."""

import json
import pathlib
import sys

SKILL = pathlib.Path("/Users/haseeb/.pi/agent/skills/create-template-for-railway/scripts")
sys.path.insert(0, str(SKILL))
import rw  # noqa: E402

WORKSPACE = "fc4796db-2c6c-4354-a564-d4a1d900af53"
ROOT = pathlib.Path(__file__).parent

if len(sys.argv) != 3:
    sys.exit("usage: deploy_as_stranger.py <template-code> <answers.json>")
code = sys.argv[1]
answers = json.loads(pathlib.Path(sys.argv[2]).read_text())
template = rw.gql(
    "query($code:String!){ template(code:$code){ id serializedConfig } }",
    {"code": code},
)["template"]
config = template["serializedConfig"]
for service in config["services"].values():
    for key, value in answers.get(service["name"], {}).items():
        service.setdefault("variables", {}).setdefault(key, {})["defaultValue"] = value
result = rw.gql(
    """mutation($input: TemplateDeployV2Input!) {
         templateDeployV2(input: $input) { projectId workflowId }
       }""",
    {
        "input": {
            "templateId": template["id"],
            "workspaceId": WORKSPACE,
            "serializedConfig": config,
        }
    },
)["templateDeployV2"]
state = ROOT / ".state" / "scratch.json"
state.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
