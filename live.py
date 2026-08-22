#!/usr/bin/env python3
"""Show service status and logs for the source or scratch project."""

import json
import pathlib
import sys

SKILL = pathlib.Path("/Users/haseeb/.pi/agent/skills/create-template-for-railway/scripts")
sys.path.insert(0, str(SKILL))
import rw  # pyright: ignore[reportMissingImports]

ROOT = pathlib.Path(__file__).parent
kind = sys.argv[1] if len(sys.argv) > 1 else "source"
command = sys.argv[2] if len(sys.argv) > 2 else "status"
state = json.loads((ROOT / ".state" / f"{kind}.json").read_text())
project_id = state["projectId"]
project = rw.gql(
    """query($id: String!) {
         project(id: $id) {
           environments { edges { node { id name } } }
           services { edges { node { id name } } }
         }
       }""",
    {"id": project_id},
)["project"]
environment_id = next(
    edge["node"]["id"] for edge in project["environments"]["edges"]
    if edge["node"]["name"] == "production"
)
services = {edge["node"]["name"]: edge["node"]["id"] for edge in project["services"]["edges"]}


def latest(service_id):
    edges = rw.gql(
        """query($project:String!, $environment:String!, $service:String!) {
             deployments(first:1, input:{projectId:$project, environmentId:$environment, serviceId:$service}) {
               edges { node { id status createdAt } }
             }
           }""",
        {"project": project_id, "environment": environment_id, "service": service_id},
    )["deployments"]["edges"]
    return edges[0]["node"] if edges else None


if command == "status":
    for name, service_id in sorted(services.items()):
        deployment = latest(service_id)
        status = deployment["status"] if deployment else "NO_DEPLOY"
        deployment_id = deployment["id"] if deployment else ""
        print(f"{name:12} {status:12} {deployment_id}")
elif command == "logs":
    if len(sys.argv) < 4:
        sys.exit("usage: live.py <source|scratch> logs <service>")
    name = sys.argv[3]
    deployment = latest(services[name])
    if not deployment:
        sys.exit(f"no deployment for {name}")
    for field in ("buildLogs", "deploymentLogs"):
        lines = rw.gql(
            f"query($id:String!){{ {field}(deploymentId:$id, limit:200){{ message severity }} }}",
            {"id": deployment["id"]},
        )[field]
        if lines:
            print(f"# {field} ({deployment['status']})")
            for line in lines:
                print(line["message"])
else:
    sys.exit(f"unknown command: {command}")
