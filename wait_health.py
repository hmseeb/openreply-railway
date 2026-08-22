#!/usr/bin/env python3
"""Wait until a source or scratch project is deployed and its full healthcheck is green."""

import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

SKILL = pathlib.Path("/Users/haseeb/.pi/agent/skills/create-template-for-railway/scripts")
sys.path.insert(0, str(SKILL))
import rw  # pyright: ignore[reportMissingImports]

ROOT = pathlib.Path(__file__).parent
kind = sys.argv[1] if len(sys.argv) > 1 else "source"
state_path = ROOT / ".state" / f"{kind}.json"
state = json.loads(state_path.read_text())
project_id = state["projectId"]
last_line = None

for _ in range(90):
    project = rw.gql(
        """query($id:String!){
             project(id:$id){
               environments { edges { node { id name } } }
               services { edges { node {
                 id name
                 serviceInstances { edges { node {
                   latestDeployment { id status }
                   domains { serviceDomains { domain targetPort } }
                 } } }
               } } }
             }
           }""",
        {"id": project_id},
    )["project"]
    statuses = {}
    services = {}
    origin = state.get("origin")
    for edge in project["services"]["edges"]:
        service = edge["node"]
        services[service["name"]] = service["id"]
        instances = service["serviceInstances"]["edges"]
        deployment = instances[0]["node"]["latestDeployment"] if instances else None
        statuses[service["name"]] = deployment["status"] if deployment else "NO_DEPLOY"
        if service["name"] == "web" and instances:
            domains = instances[0]["node"]["domains"]["serviceDomains"]
            if domains:
                origin = f"https://{domains[0]['domain']}"

    health = None
    if origin:
        try:
            with urllib.request.urlopen(f"{origin}/api/health", timeout=15) as response:
                health = json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            health = None

    line = f"deployments={statuses} health={health and health.get('status')}"
    if line != last_line:
        print(line, flush=True)
        last_line = line

    terminal_failures = {"FAILED", "CRASHED", "REMOVED"}
    if any(status in terminal_failures for status in statuses.values()):
        sys.exit("a service deployment failed")
    worker_ok = bool(health and health.get("checks", {}).get("worker", {}).get("healthy"))
    if statuses and all(status == "SUCCESS" for status in statuses.values()) and health and health.get("status") == "ok" and worker_ok:
        environment_id = next(
            edge["node"]["id"]
            for edge in project["environments"]["edges"]
            if edge["node"]["name"] == "production"
        )
        state.update(
            {
                "environmentId": environment_id,
                "origin": origin,
                "services": services,
                "health": health,
            }
        )
        state_path.write_text(json.dumps(state, indent=2) + "\n")
        print(f"healthy {origin}")
        raise SystemExit(0)
    time.sleep(10)

sys.exit("project did not become healthy within 15 minutes")
