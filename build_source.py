#!/usr/bin/env python3
"""Build the OpenReply regeneration project in the Auromations workspace."""

import json
import pathlib
import secrets
import string
import sys

SKILL = pathlib.Path("/Users/haseeb/.pi/agent/skills/create-template-for-railway/scripts")
sys.path.insert(0, str(SKILL))
import rw  # noqa: E402

WORKSPACE = "fc4796db-2c6c-4354-a564-d4a1d900af53"
APP_IMAGE = "ghcr.io/hmseeb/openreply-railway:1.0.0"
POSTGRES_IMAGE = "ghcr.io/railwayapp-templates/postgres-ssl:16"
REDIS_IMAGE = "redis:8.2"
STATE = pathlib.Path(__file__).parent / ".state" / "source.json"
ICON = "https://raw.githubusercontent.com/diwenne/openreply/80fa38780e2973a0299c05019bc0d0657044220c/public/icon-512.png"


def rand(length=32, alphabet=string.ascii_letters + string.digits):
    return "".join(secrets.choice(alphabet) for _ in range(length))


def gql(document, variables=None):
    return rw.gql(document, variables)


def create_service(project_id, environment_id, name, image, variables, *, start=None, health=None):
    service = gql(
        """mutation($input: ServiceCreateInput!) {
             serviceCreate(input: $input) { id name }
           }""",
        {
            "input": {
                "projectId": project_id,
                "environmentId": environment_id,
                "name": name,
                "source": {"image": image},
                "variables": variables,
            }
        },
    )["serviceCreate"]
    update = {"restartPolicyType": "ON_FAILURE"}
    if start:
        update["startCommand"] = start
    if health:
        update["healthcheckPath"] = health
    gql(
        """mutation($serviceId: String!, $environmentId: String!, $input: ServiceInstanceUpdateInput!) {
             serviceInstanceUpdate(serviceId: $serviceId, environmentId: $environmentId, input: $input)
           }""",
        {"serviceId": service["id"], "environmentId": environment_id, "input": update},
    )
    print(f"created {name}: {service['id']}")
    return service["id"]


def add_volume(project_id, environment_id, service_id, mount_path):
    return gql(
        """mutation($input: VolumeCreateInput!) { volumeCreate(input: $input) { id } }""",
        {
            "input": {
                "projectId": project_id,
                "environmentId": environment_id,
                "serviceId": service_id,
                "mountPath": mount_path,
            }
        },
    )["volumeCreate"]["id"]


def main():
    project = gql(
        """mutation($input: ProjectCreateInput!) {
             projectCreate(input: $input) {
               id
               environments { edges { node { id name } } }
             }
           }""",
        {"input": {"name": "openreply-source", "workspaceId": WORKSPACE}},
    )["projectCreate"]
    project_id = project["id"]
    environment_id = next(
        edge["node"]["id"]
        for edge in project["environments"]["edges"]
        if edge["node"]["name"] == "production"
    )
    print(f"project: {project_id}")

    postgres_password = rand()
    postgres = create_service(
        project_id,
        environment_id,
        "postgres",
        POSTGRES_IMAGE,
        {
            "PGDATA": "/var/lib/postgresql/data/pgdata",
            "POSTGRES_DB": "openreply",
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": postgres_password,
            "SSL_CERT_DAYS": "820",
            "RAILWAY_DEPLOYMENT_DRAINING_SECONDS": "60",
        },
    )
    add_volume(project_id, environment_id, postgres, "/var/lib/postgresql/data")

    redis_password = rand()
    redis = create_service(
        project_id,
        environment_id,
        "redis",
        REDIS_IMAGE,
        {"REDIS_PASSWORD": redis_password},
        start=(
            '/bin/sh -c "rm -rf $RAILWAY_VOLUME_MOUNT_PATH/lost+found/ '
            '&& exec docker-entrypoint.sh redis-server --requirepass $REDIS_PASSWORD '
            '--save 60 1 --dir $RAILWAY_VOLUME_MOUNT_PATH"'
        ),
    )
    add_volume(project_id, environment_id, redis, "/data")

    database_url = (
        f"postgresql://postgres:{postgres_password}@postgres.railway.internal:5432/openreply"
    )
    redis_url = f"redis://default:{redis_password}@redis.railway.internal:6379"
    shared = {
        "DATABASE_URL": database_url,
        "REDIS_URL": redis_url,
        "NEXTAUTH_SECRET": rand(),
        "ENCRYPTION_KEY": rand(64, "0123456789abcdef"),
        "INSTAGRAM_APP_ID": "replace-after-deploy",
        "INSTAGRAM_APP_SECRET": "replace-after-deploy",
        "FACEBOOK_APP_SECRET": "replace-after-deploy",
        "WEBHOOK_VERIFY_TOKEN": rand(),
        "META_GRAPH_API_VERSION": "v25.0",
        "COMMENT_POLL_INTERVAL_MS": "300000",
        "COMMENT_POLL_MAX_PER_SWEEP": "30",
        "COMMENT_POLL_LOOKBACK_HOURS": "72",
    }
    web = create_service(
        project_id,
        environment_id,
        "web",
        APP_IMAGE,
        {
            **shared,
            "PORT": "3000",
            "NEXTAUTH_URL": "https://placeholder.invalid",
            "CRON_SECRET": rand(),
            "RESEND_API_KEY": "re_replace_after_deploy",
            "EMAIL_FROM": "OpenReply <login@example.com>",
        },
        start="/usr/local/bin/boot.sh web",
        health="/api/health",
    )
    domain = gql(
        """mutation($input: ServiceDomainCreateInput!) {
             serviceDomainCreate(input: $input) { domain }
           }""",
        {
            "input": {
                "environmentId": environment_id,
                "serviceId": web,
                "targetPort": 3000,
            }
        },
    )["serviceDomainCreate"]["domain"]
    origin = f"https://{domain}"
    gql(
        """mutation($input: VariableCollectionUpsertInput!) {
             variableCollectionUpsert(input: $input)
           }""",
        {
            "input": {
                "projectId": project_id,
                "environmentId": environment_id,
                "serviceId": web,
                "replace": False,
                "variables": {"NEXTAUTH_URL": origin},
            }
        },
    )

    worker = create_service(
        project_id,
        environment_id,
        "worker",
        APP_IMAGE,
        {**shared, "NEXTAUTH_URL": origin},
        start="/usr/local/bin/boot.sh worker",
    )

    for service_id in (web, worker):
        gql(
            """mutation($serviceId: String!, $environmentId: String!) {
                 serviceInstanceDeployV2(serviceId: $serviceId, environmentId: $environmentId)
               }""",
            {"serviceId": service_id, "environmentId": environment_id},
        )

    state = {
        "projectId": project_id,
        "environmentId": environment_id,
        "origin": origin,
        "services": {"postgres": postgres, "redis": redis, "web": web, "worker": worker},
        "icon": ICON,
    }
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2) + "\n")
    print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
