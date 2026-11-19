# Deploy and Host OpenReply on Railway

OpenReply is an open source Instagram comment-to-DM tool. A person comments a keyword named in your post, Meta sends the event to your deployment, and an always-on worker sends the private reply through Meta's official API. It includes campaign analytics, tracked links, an inbox, workspaces, and DM logs without seat limits or plan caps.

## About Hosting OpenReply

This template deploys the Next.js web app, a long-running BullMQ worker, a small cron scheduler, Postgres, and Redis. The web service receives users, OAuth callbacks, and Meta webhooks. The worker survives retries and rate-limit windows, and polls every five minutes for comments that webhooks missed. The cron service calls the web app over the private network to refresh Instagram tokens daily, so connected accounts keep working past the 60-day token lifetime.

Only the web service is public. Railway generates the database and Redis credentials, a session secret, the Instagram-token encryption key, the cron secret, and the webhook verification token. The `/api/health` endpoint returns 200 only when Postgres, Redis, the queue, and the worker heartbeat are all healthy.

OpenReply sends messages to third parties, so use it only for explicit opt-in campaigns. The post must say that commenting a named keyword triggers a DM, and the campaign must match that keyword. Do not enable **Match any word** to message every commenter. OpenReply uses Meta's official API, deduplicates each comment, and enforces Meta's documented 750 private replies per account per hour.

## Common Use Cases

- Send a requested guide, download, product link, or event link after someone comments the CTA keyword.
- Run comment campaigns for several professional Instagram accounts in one workspace.
- Track link clicks and conversion rates per campaign while keeping campaign and account data in your own database.
- Give a small team owner, admin, and member access without per-seat pricing.

## Dependencies for OpenReply Hosting

- A Meta Business app with Instagram messaging and comments permissions.
- An Instagram Business or Creator account. Personal accounts cannot connect.
- A Resend account with a verified sender domain for login magic links.
- Postgres and Redis, both included in this template.

### Deployment Dependencies

- Source: [diwenne/openreply](https://github.com/diwenne/openreply), MIT licensed, pinned to commit `c78b2d2f68c9764ef7a7dde51dfa5bfa99304a09`.
- Image: [hmseeb/openreply-railway](https://github.com/hmseeb/openreply-railway), tag `1.1.0`.
- [Meta app setup guide](https://github.com/diwenne/openreply/blob/c78b2d2f68c9764ef7a7dde51dfa5bfa99304a09/docs/setup.md)
- [Resend](https://resend.com)

### Implementation Details

**Values requested during deployment**

| Variable | Where to get it |
| --- | --- |
| `RESEND_API_KEY` | Resend API keys |
| `EMAIL_FROM` | A sender on a domain verified in Resend, such as `login@example.com`, optionally with a display name before it in angle brackets |
| `INSTAGRAM_APP_ID` | Meta, Instagram product, API setup with Instagram login |
| `INSTAGRAM_APP_SECRET` | The same Instagram product page |
| `FACEBOOK_APP_SECRET` | Meta App Settings, Basic |

Optional: set `ALLOWED_EMAILS` to a comma-separated list to restrict who can sign in. Without it, anyone who reaches the URL can create a workspace.

The Facebook app ID is not the Instagram product app ID. OpenReply needs the Instagram product ID plus both secrets.

**Expected first boot**

The web and worker both run Prisma migrations with bounded retries while Postgres starts. `/api/health` can return 503 for about 1 to 2 minutes. It becomes 200 only after the worker writes its Redis heartbeat. No manual database migration is needed.

**Meta configuration after deployment**

1. Copy the `web` public domain.
2. Register `https://YOUR-WEB-DOMAIN/api/instagram/callback` as the Instagram OAuth redirect.
3. Register `https://YOUR-WEB-DOMAIN/api/webhook` as the webhook callback.
4. Copy `WEBHOOK_VERIFY_TOKEN` from the `web` service into Meta's verify-token field.
5. Subscribe to `comments`.
6. Add your professional Instagram account as a tester and accept the invite inside Instagram.
7. Put the Meta app in Live mode before testing a real comment.

Standard Access only covers accounts that hold a role on your app. A published Meta app does not automatically let unrelated accounts connect. For other customers, complete App Review for Advanced Access and Meta business verification.

**Test the real journey**

Request a login magic link, connect an accepted tester account, and create a campaign with keyword `TEST`. State in the post that commenting `TEST` sends a DM. Comment from another Instagram account because self-comments are ignored. Confirm the private reply arrives and the DM Logs page records `SENT`.

**Troubleshooting**

- `/api/health` says the worker is unhealthy: inspect the worker deployment and confirm its database URL, Redis URL, and encryption key reference the same values as `web`.
- Login email does not arrive: verify the Resend key and sender domain. SMTP is supported later through an `EMAIL_SERVER` variable on `web`.
- Instagram reports Insufficient Developer Role: send the tester invite in Meta and accept it inside Instagram.
- OAuth reports redirect mismatch: use the exact HTTPS web domain with `/api/instagram/callback` and no trailing slash.
- Meta's test event works but real comments do not: set the app to Live and confirm the `comments` subscription.
- A second account receives IGApiException code 100: that account needs its own accepted tester role or the app needs Advanced Access.

**Persistence, upgrades, and scaling**

Postgres stores durable app data and encrypted Instagram tokens. Redis stores queue jobs, delayed retries, rate limits, and health state. Both have volumes. Back them up before major upgrades.

Start with one worker. More workers increase concurrency and pressure against Meta limits. The application image is pinned to an exact commit, so upgrades are deliberate rather than silently following upstream `main`.

## Why Deploy OpenReply on Railway?

OpenReply is not only a web page. A webhook receiver, queue consumer, polling reconciler, cron scheduler, Postgres, and Redis must stay online and share exact secrets. Railway runs every piece on one private network, keeps both datastores persistent, and restarts the worker when it fails.

The template also removes the fragile setup steps from the runtime: Prisma migrations run after the services can reach Postgres, the web listener supports Railway's IPv6 network, the public domain targets port 3000 explicitly, and the healthcheck waits for the worker rather than reporting a false green web page.
