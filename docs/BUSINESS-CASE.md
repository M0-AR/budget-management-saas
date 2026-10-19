# Budgetary — business case

**For:** owners, operators and finance leads evaluating a shared budgeting
workspace. **Decision:** run the demo, then decide whether self-hosting is a
better fit than a spreadsheet or a per-seat subscription.

## Executive summary

Budgetary is a complete budgeting workspace that a household, studio or small
team can run on its own server. It replaces the shared spreadsheet and the
shared login with individual accounts, enforced roles and one private workspace
per team. The source is MIT licensed, so there are no seat fees, no usage meter
and no vendor holding the data. The trade-off is equally clear: you operate the
server, the backups and the upgrades.

## The problem with the workaround

A spreadsheet is cheap until more than one person needs it. Then the hidden
costs appear:

- **Duplicate entry.** Two people record the same expense, or neither does.
- **Status chasing.** “Did we pay it?” becomes a message, not a lookup.
- **Month-end reconstruction.** Reports are rebuilt by hand from incomplete rows.
- **Weak access control.** A shared file or password cannot express “read-only”
  or “admin”.
- **No audit story.** When a number changes, nobody knows who changed it.
- **Tool sprawl.** The budget lives in one file, receipts in another, and the
  branded customer experience nowhere.

None of these is a spreadsheet bug. They are coordination costs.

## What changes

| Before | After |
| --- | --- |
| One shared file and password | One private workspace with individual logins |
| Everyone can edit everything | Owner, admin, member and viewer roles enforced by the API |
| Numbers scattered across tabs | Dashboard, expenses, income, budgets and reports on one model |
| “Are we okay?” answered manually | Utilisation, remaining balance, status and spending pace |
| Month-end rebuilt by hand | Monthly and yearly reports, CSV export and a six-month trend |
| Generic tool, generic login | Per-workspace name, accent colour, logo, currency, locale and timezone |
| No record of changes | Append-only audit trail for logins, money, imports, roles and branding |
| Vendor lock-in | MIT source, PostgreSQL and Docker Compose |

## Who benefits

- **The person who tracks the money** spends less time reconciling and more time
  answering questions with a current dashboard.
- **The people who share the money** get their own login and the access level
  they need, without passing a password around.
- **The person accountable for it** gets a repeatable month-end process, an
  audit trail and a portable export.
- **The person running the server** gets one Compose stack, health endpoints,
  automatic migrations and a documented tenant boundary.
- **A privacy-sensitive buyer** keeps the data on infrastructure they control,
  with no external analytics or AI calls.

## Cost model — use your own numbers

Do not accept a vendor’s claimed saving. Calculate the current routine:

```
people × hours per person per month × fully loaded hourly cost = monthly routine cost
monthly routine cost × 12 = annual routine cost
```

Example: **4 people × 3 hours × $45 = $540 per month, or $6,480 per year.**

That is the cost of the routine, not a promise that Budgetary removes all of it.
It gives you a number to compare with the server, backup and administration
time you will own. The interactive calculator in the product tour does the same
arithmetic with your inputs.

Budgetary’s software licence cost is **$0**. Your real costs are:

- a Linux server or an existing machine,
- backups and monitoring,
- the time to deploy, patch and review access,
- optional paid help if you want it.

## Build vs buy vs spreadsheet

| Option | Cash cost | Time cost | Access control | Data ownership | Main risk |
| --- | --- | --- | --- | --- | --- |
| Shared spreadsheet | Low | Hidden and recurring | Weak | File owner | Drift, duplicate entry, no audit |
| Build in-house | High | Weeks to months, then ongoing | Whatever you build | Yours | Scope creep, security mistakes, maintenance |
| Hosted budgeting SaaS | Per seat, recurring | Low at first | Usually good | Vendor | Lock-in, price changes, data leaves your control |
| **Budgetary (self-hosted)** | Server + your time | Days to deploy, ongoing ops | RLS + four roles | Yours | You own patching, backups and availability |

Budgetary is not automatically cheaper. It is cheaper when you value data
control, avoid per-seat pricing, and can absorb routine operations — or already
have someone who can.

## Evaluation scorecard

| Criterion | Pass condition | Where to check |
| --- | --- | --- |
| Fit | The team shares one monthly limit and needs separate logins | [Five-minute tour](../README.md#a-five-minute-tour) |
| Isolation | A second workspace cannot read or attach the first workspace’s rows | Security section and tests |
| Roles | Viewer writes are rejected by the API, not only hidden in the UI | Members settings |
| Migration | A CSV with aliases and one bad row produces row-level errors | Expenses → Import |
| Portability | Transactions export to CSV; the database volume can be backed up | Reports, deployment docs |
| Brand | Name, accent, logo, currency and locale follow the workspace | Settings → Workspace |
| Operations | Health and readiness endpoints work; migrations run on boot | `/healthz`, `/readyz` |
| Honest scope | The limitations are acceptable | [What it does not do](../README.md#what-it-does-not-do) |

## A 30-day rollout

1. **Week 1 — evaluate.** Run the Compose stack, complete the ten-minute
   evaluation, and have whoever owns security read the isolation model.
2. **Week 2 — prepare.** Choose the host, set real secrets, enable TLS, configure
   backups, and decide who holds owner and admin roles.
3. **Week 3 — migrate.** Export the current spreadsheet to CSV, import a copy with
   duplicates skipped, and fix row-level errors before inviting the team.
4. **Week 4 — run in parallel.** Keep the old process for one month, compare the
   numbers, then retire the shared file and password.

## Procurement answers

- **Licence:** MIT. Commercial and internal use are permitted; keep the copyright
  and licence notice when redistributing source.
- **Hosting:** self-hosted with Docker Compose. No managed service is included.
- **Data location:** the PostgreSQL volume on your infrastructure.
- **Access:** individual accounts, four enforced roles, rotating sessions.
- **Isolation:** forced PostgreSQL row-level security plus a non-superuser app
  role and per-transaction tenant context.
- **Portability:** CSV transaction export and a standard PostgreSQL backup.
- **Certifications:** none claimed. This is not a SOC 2, ISO 27001 or HIPAA
  product. Your procurement review still owns patching, backups, secrets and
  access policy.
- **Support:** self-support with the documentation and tests in the repository.
  Any commercial support or custom work is a separate arrangement.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| The team lacks server skills | Use one small host, follow the runbook, or buy implementation help |
| A secret leaks | Change every default in `.env`; keep it out of version control |
| Backups are forgotten | Schedule PostgreSQL volume backups and test a restore |
| Traffic grows beyond one API replica | Move the in-process rate limiter to Redis before scaling out |
| The team needs bank sync or SSO | Treat those as out of scope for this build, not as hidden features |
| The licence is misunderstood | MIT permits commercial use; it does not include support or warranty |

## What would make you say no

Say no if you need bank feeds, receipt OCR, many independent budget pots, SSO,
a native mobile app, a certified compliance programme, or a vendor who is
contractually responsible for uptime. Those are legitimate requirements; this
build does not pretend to meet them.

## Next step

Run the demo and complete the ten-minute evaluation in the
[README](../README.md#ten-minute-evaluation). If the scorecard passes, deploy a
staging copy and import one real month of data before inviting the team.
