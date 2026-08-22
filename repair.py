#!/usr/bin/env python3
"""Repair generated config, save it as a new editable draft, and assert it back."""

import json
import pathlib
import re
import sys
import uuid

SKILL = pathlib.Path("/Users/haseeb/.pi/agent/skills/create-template-for-railway/scripts")
sys.path.insert(0, str(SKILL))
import rw  # pyright: ignore[reportMissingImports]

WORKSPACE = "fc4796db-2c6c-4354-a564-d4a1d900af53"
NAME = "OpenReply"
APP_IMAGE = "ghcr.io/hmseeb/openreply-railway:1.0.0"
ICON = "https://raw.githubusercontent.com/diwenne/openreply/80fa38780e2973a0299c05019bc0d0657044220c/public/icon-512.png"


def var(default=None, *, optional=False, description=None):
    spec = {"isOptional": optional}
    if default is not None:
        spec["defaultValue"] = default
    if description:
        spec["description"] = description
    return spec


POSTGRES = {
    "PGDATA": var("/var/lib/postgresql/data/pgdata", description="Database files use a subdirectory because Railway volume roots contain lost+found"),
    "PGHOST": var("${{RAILWAY_PRIVATE_DOMAIN}}"),
    "PGPORT": var("5432"),
    "PGUSER": var("${{POSTGRES_USER}}"),
    "PGDATABASE": var("${{POSTGRES_DB}}"),
    "PGPASSWORD": var("${{POSTGRES_PASSWORD}}"),
    "POSTGRES_DB": var("openreply"),
    "POSTGRES_USER": var("postgres"),
    "POSTGRES_PASSWORD": var('${{ secret(32, "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ") }}'),
    "DATABASE_URL": var("postgresql://${{PGUSER}}:${{POSTGRES_PASSWORD}}@${{RAILWAY_PRIVATE_DOMAIN}}:5432/${{PGDATABASE}}"),
    "SSL_CERT_DAYS": var("820", optional=True),
    "RAILWAY_DEPLOYMENT_DRAINING_SECONDS": var("60", description="Allow Postgres to shut down cleanly"),
}

REDIS = {
    "REDISHOST": var("${{RAILWAY_PRIVATE_DOMAIN}}"),
    "REDISPORT": var("6379"),
    "REDISUSER": var("default"),
    "REDIS_PASSWORD": var('${{ secret(32, "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ") }}'),
    "REDISPASSWORD": var("${{REDIS_PASSWORD}}"),
    "REDIS_URL": var("redis://${{REDISUSER}}:${{REDIS_PASSWORD}}@${{REDISHOST}}:${{REDISPORT}}"),
}

WEB = {
    "PORT": var("3000"),
    "NEXTAUTH_URL": var("https://${{RAILWAY_PUBLIC_DOMAIN}}"),
    "NEXTAUTH_SECRET": var("${{secret(32)}}"),
    "CRON_SECRET": var("${{secret(32)}}"),
    "ENCRYPTION_KEY": var('${{ secret(64, "0123456789abcdef") }}', description="Exactly 64 hexadecimal characters; shared with the worker to encrypt Instagram tokens"),
    "DATABASE_URL": var("${{postgres.DATABASE_URL}}"),
    "REDIS_URL": var("${{redis.REDIS_URL}}"),
    "RESEND_API_KEY": var(description="Resend API key used for login magic links. Use a key authorized for the EMAIL_FROM domain"),
    "EMAIL_FROM": var(description="Verified sender, for example OpenReply <login@example.com>"),
    "META_GRAPH_API_VERSION": var("v25.0"),
    "INSTAGRAM_APP_ID": var(description="Instagram product app ID from Meta, not the Facebook app ID"),
    "INSTAGRAM_APP_SECRET": var(description="Instagram product app secret from Meta"),
    "FACEBOOK_APP_SECRET": var(description="Facebook app secret from Meta App Settings, used to verify webhook signatures"),
    "WEBHOOK_VERIFY_TOKEN": var("${{secret(32)}}", description="Paste this generated value into Meta webhook configuration after deployment"),
}

WORKER = {
    "NEXTAUTH_URL": var("https://${{web.RAILWAY_PUBLIC_DOMAIN}}"),
    "NEXTAUTH_SECRET": var("${{web.NEXTAUTH_SECRET}}"),
    "ENCRYPTION_KEY": var("${{web.ENCRYPTION_KEY}}"),
    "DATABASE_URL": var("${{postgres.DATABASE_URL}}"),
    "REDIS_URL": var("${{redis.REDIS_URL}}"),
    "META_GRAPH_API_VERSION": var("${{web.META_GRAPH_API_VERSION}}"),
    "INSTAGRAM_APP_ID": var("${{web.INSTAGRAM_APP_ID}}"),
    "INSTAGRAM_APP_SECRET": var("${{web.INSTAGRAM_APP_SECRET}}"),
    "FACEBOOK_APP_SECRET": var("${{web.FACEBOOK_APP_SECRET}}"),
    "WEBHOOK_VERIFY_TOKEN": var("${{web.WEBHOOK_VERIFY_TOKEN}}"),
    "COMMENT_POLL_INTERVAL_MS": var("300000", description="Poll every five minutes for comments missed by webhooks"),
    "COMMENT_POLL_MAX_PER_SWEEP": var("30", description="Conservative per-campaign cap for each polling sweep"),
    "COMMENT_POLL_LOOKBACK_HOURS": var("72"),
}

VARIABLES = {"postgres": POSTGRES, "redis": REDIS, "web": WEB, "worker": WORKER}
ICONS = {
    "postgres": "https://devicons.railway.app/i/postgresql.svg",
    "redis": "https://cdn.sanity.io/images/sy1jschh/production/0ce0bfdcfbdbf69662b1116671f97c2dd788b655-157x157.svg",
    "web": ICON,
    "worker": ICON,
}
DEPLOY = {
    "postgres": {"restartPolicyType": "ON_FAILURE", "restartPolicyMaxRetries": 10},
    "redis": {
        "startCommand": '/bin/sh -c "rm -rf $RAILWAY_VOLUME_MOUNT_PATH/lost+found/ && exec docker-entrypoint.sh redis-server --requirepass $REDIS_PASSWORD --save 60 1 --dir $RAILWAY_VOLUME_MOUNT_PATH"',
        "restartPolicyType": "ON_FAILURE",
        "restartPolicyMaxRetries": 10,
    },
    "web": {
        "startCommand": "/usr/local/bin/boot.sh web",
        "healthcheckPath": "/login",
        "restartPolicyType": "ON_FAILURE",
        "restartPolicyMaxRetries": 10,
    },
    "worker": {
        "startCommand": "/usr/local/bin/boot.sh worker",
        "restartPolicyType": "ON_FAILURE",
        "restartPolicyMaxRetries": 10,
    },
}


def fresh_ids(config):
    remap = {service_id: str(uuid.uuid4()) for service_id in config["services"]}
    services = {}
    for old_id, original in config["services"].items():
        service = json.loads(json.dumps(original))
        if service.get("volumeMounts"):
            service["volumeMounts"] = {remap[key]: value for key, value in service["volumeMounts"].items()}
        services[remap[old_id]] = service
    return {"buckets": config.get("buckets", {}), "services": services}


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: repair.py <new|template-id> <generated.json>")
    template_id, path = sys.argv[1:]
    payload = json.loads(pathlib.Path(path).read_text())
    config = payload.get("templateGenerate", payload)
    config = config.get("serializedConfig", config)

    if template_id == "new":
        template_id = str(uuid.uuid4())
        config = fresh_ids(config)
        print(f"minting draft {template_id}")

    for service in config["services"].values():
        name = service["name"]
        if name not in VARIABLES:
            raise RuntimeError(f"unexpected generated service: {name}")
        service["variables"] = VARIABLES[name]
        service["icon"] = ICONS[name]
        service["deploy"] = DEPLOY[name]
        if name in ("web", "worker"):
            service["source"] = {"image": APP_IMAGE}
        if name == "web":
            service["networking"] = {"serviceDomains": {"<hasDomain>:3000": {"port": 3000}}}

    saved = rw.gql(
        """mutation($id: String!, $input: TemplateUpsertConfigInput!) {
             templateUpsertConfig(id: $id, input: $input) { id code }
           }""",
        {
            "id": template_id,
            "input": {
                "name": NAME,
                "workspaceId": WORKSPACE,
                "serializedConfig": config,
                "canvasConfig": {},
            },
        },
        internal=True,
    )["templateUpsertConfig"]
    print(f"saved id={saved['id']} code={saved['code']}")

    back = rw.gql(
        "query($code:String!){ template(code:$code){ serializedConfig } }",
        {"code": saved["code"]},
    )["template"]["serializedConfig"]
    problems = []
    by_name = {service["name"]: service for service in back["services"].values()}
    if set(by_name) != set(VARIABLES):
        problems.append(f"services are {sorted(by_name)}, wanted {sorted(VARIABLES)}")
    for name, wanted_variables in VARIABLES.items():
        service = by_name.get(name, {})
        got_variables = service.get("variables", {})
        for key, wanted in wanted_variables.items():
            if got_variables.get(key, {}).get("defaultValue") != wanted.get("defaultValue"):
                problems.append(f"{name}.{key} default mismatch")
            if key not in got_variables:
                problems.append(f"{name}.{key} missing")
        for key, wanted in DEPLOY[name].items():
            if service.get("deploy", {}).get(key) != wanted:
                problems.append(f"{name}.deploy.{key} mismatch")
    web_network = by_name.get("web", {}).get("networking", {}).get("serviceDomains", {})
    if not any(domain.get("port") == 3000 for domain in web_network.values()):
        problems.append("web target port 3000 missing")

    for reference in re.findall(r"\$\{\{[^}]*\}\}", json.dumps(back)):
        if re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-", reference):
            problems.append(f"reference keyed by UUID: {reference}")

    for problem in problems:
        print("MISMATCH", problem)
    if problems:
        sys.exit(f"{len(problems)} config mismatches")

    state = pathlib.Path(__file__).parent / ".state" / "template.json"
    state.parent.mkdir(exist_ok=True)
    state.write_text(json.dumps(saved, indent=2) + "\n")
    print("clean")


if __name__ == "__main__":
    main()
