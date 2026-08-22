# OpenReply on Railway

OpenReply turns an explicit Instagram comment keyword into a private reply through Meta's official API. This repository packages upstream commit [`80fa387`](https://github.com/diwenne/openreply/commit/80fa38780e2973a0299c05019bc0d0657044220c) as a Railway-ready image and four-service template.

Upstream: [diwenne/openreply](https://github.com/diwenne/openreply), MIT licensed.

## What gets deployed

| Service | Purpose |
| --- | --- |
| `web` | Next.js dashboard, authentication, OAuth callback, and Meta webhook on port 3000 |
| `worker` | Always-on BullMQ consumer and missed-comment poller |
| `postgres` | Users, workspaces, campaigns, encrypted Instagram tokens, and logs |
| `redis` | Queue jobs, delayed retries, rate limits, and worker heartbeat |

The web and worker share the same database URL, Redis URL, and 64-character hexadecimal encryption key. Railway generates and wires those values. Only `web` gets a public domain.

## Before deploying

Have these values ready:

1. A Resend API key and a verified sender such as `OpenReply <login@example.com>`.
2. A Meta Business app with the Instagram messaging use case.
3. The Instagram product app ID and secret, plus the Facebook app secret.
4. An Instagram Business or Creator account.

The code deploy takes about 5 minutes. Meta setup can take an afternoon the first time.

## Required opt-in rule

Use OpenReply only when the post explicitly tells people that commenting a named keyword will trigger a DM. Create keyword campaigns for that CTA. Do not use **Match any word** to message every commenter.

This keeps each private reply tied to a clear user action. OpenReply already uses Meta's official API, deduplicates comments, and caps each account at Meta's documented 750 private replies per hour. The template cannot enforce the campaign setting, so the deployer must.

## After deployment

1. Wait for `GET https://<web-domain>/api/health` to return `status: ok` with `worker.healthy: true`.
2. In Meta, set the Instagram OAuth redirect to `https://<web-domain>/api/instagram/callback`.
3. Set the Meta webhook callback to `https://<web-domain>/api/webhook` and copy `WEBHOOK_VERIFY_TOKEN` from the `web` service.
4. Subscribe the webhook to `comments`, accept the Instagram tester invite, and put the Meta app in Live mode.
5. Request a login magic link, connect Instagram, and create a keyword campaign.

Standard Access works only for accounts with a role on the Meta app. Hosting for unrelated customers needs Advanced Access, App Review, and usually Meta business verification.

## Verify the full flow

1. Create a campaign on a post with keyword `TEST` and write in the post CTA that `TEST` triggers a DM.
2. Comment `TEST` from a different Instagram account. Self-comments are intentionally ignored.
3. Confirm the DM arrives and the dashboard shows a `SENT` DM log.

If it fails, inspect these in order:

- `WebhookEvent`: whether Meta reached the web service.
- `DmLog`: whether a campaign matched and what Meta returned.
- `OperationalEvent`: worker, polling, and token-refresh errors.
- `/api/health`: database, Redis, queue, and worker heartbeat status.

## Common failures

**Health is degraded and worker is unhealthy.** Check the worker deployment first. Both app roles must use the same `REDIS_URL`, `DATABASE_URL`, and `ENCRYPTION_KEY`.

**No login email arrives.** `RESEND_API_KEY` must be valid and `EMAIL_FROM` must use a domain verified in Resend. You can use SMTP instead by adding `EMAIL_SERVER` to `web`.

**Instagram says Insufficient Developer Role.** Add the Instagram account as a tester in Meta, then accept the invite inside Instagram. Both halves are required.

**OAuth returns redirect_uri_mismatch.** Register the web domain plus `/api/instagram/callback`, exactly, with HTTPS and no trailing slash.

**Webhooks verify but real comments do nothing.** Meta's test event works in Development mode, but real comment webhooks require the app to be Live. Also confirm the `comments` field is subscribed.

**A second Instagram account gets IGApiException code 100.** Standard Access covers only app-role accounts. Add and accept a tester role for that account or complete App Review for Advanced Access.

## Operations

Postgres and Redis both have persistent volumes. Back them up together before a major upgrade. The app services have no filesystem state and can be replaced freely.

One worker is the intended starting size. Scaling workers raises concurrency and polling pressure against Meta. Increase it only after reviewing BullMQ concurrency and per-account rate limits.

The image is pinned to an exact upstream commit. To upgrade, change `OPENREPLY_COMMIT` in `Dockerfile`, run `test/contract.sh`, publish a new immutable image tag, and update `template.json` plus `repair.py`.

## Image contract

`test/contract.sh` verifies that the Dockerfile pins upstream source, the boot script applies Prisma migrations, the web role binds IPv6, the worker role exists, and the image builds.

Image: `ghcr.io/hmseeb/openreply-railway:1.0.0`
