#!/usr/bin/env python3
"""Generate a read-only Railway template skeleton from the source project."""

import json
import pathlib
import sys

SKILL = pathlib.Path("/Users/haseeb/.pi/agent/skills/create-template-for-railway/scripts")
sys.path.insert(0, str(SKILL))
import rw  # pyright: ignore[reportMissingImports]

ROOT = pathlib.Path(__file__).parent
state = json.loads((ROOT / ".state" / "source.json").read_text())
result = rw.gql(
    """mutation($input: TemplateGenerateInput!) {
         templateGenerate(input: $input) { id code serializedConfig }
       }""",
    {"input": {"projectId": state["projectId"], "environmentId": state["environmentId"]}},
)["templateGenerate"]
out = ROOT / ".state" / "generated.json"
out.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"id": result["id"], "code": result["code"], "path": str(out)}, indent=2))
