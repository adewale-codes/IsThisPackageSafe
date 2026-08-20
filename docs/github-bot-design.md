# GitHub bot - design sketch (stub, not implemented)

Not built this phase - this is the design so it's a scoped follow-up rather
than a blank slate. Everything below is a sketch to implement against, not
running code.

## Goal

`@packagesafe check <package>` in a PR or issue comment gets a reply comment
with that package's PackageSafe verdict, score, and top findings - same data
the badge/CLI/action show, just delivered where a reviewer is already
looking.

## Shape: GitHub App, not a raw webhook script

A GitHub App (not a personal-access-token webhook) because:

- Comments should post as **PackageSafe**, not as a maintainer's personal account.
- App installation tokens are scoped per-repo and short-lived - no long-lived PAT to leak.
- Apps get a dedicated `issue_comment` (and optionally `pull_request_review_comment`)
  webhook subscription without needing repo-admin-level access.

## Components (all stubbed)

1. **Webhook receiver** - a new route, most naturally `POST /webhooks/github`
   on the existing FastAPI backend (reuses the deployed API, no new service
   to stand up). Responsibilities:
   - Verify the `X-Hub-Signature-256` HMAC against the App's webhook secret
     before touching the payload - reject unsigned/mismatched requests with
     401 and do not process them.
   - Filter to `issue_comment` events where `action == "created"` and the
     comment body matches `/@packagesafe\s+check\s+(\S+)/i`.
   - Respond `202` immediately and do the scan+reply asynchronously (a
     background task) - GitHub expects webhook responses within ~10s, and a
     scan (especially one that triggers Phase 4's deep scan) can take longer.

2. **Installation-token exchange** - on each event, exchange the App's JWT
   (signed with the App's private key, stored as a secret) for a short-lived
   installation access token via `POST /app/installations/{id}/access_tokens`.
   Cache tokens for their ~1h lifetime rather than re-minting per comment.

3. **Scan + reply** - call the existing `scanner.scan_package()` directly
   (in-process, since this lives on the same backend) rather than round-tripping
   through the public HTTP API. Format a comment body reusing the same
   verdict/finding shapes the CLI and badge already render, e.g.:

   ```
   ## 🟡 PackageSafe: `left-pad` - suspicious (35/100)

   | Finding | Points |
   |---|---|
   | Possible typosquat of a popular package | +30 |
   | No linked source repository | +5 |

   [Full report →](https://packagesafe.dev/p/left-pad)
   ```

   Post via `POST /repos/{owner}/{repo}/issues/{issue_number}/comments` using
   the installation token.

4. **Abuse/rate protection** - stubbed, but the shape: per-installation rate
   limit (e.g. N checks/hour) held in the same in-process cache pattern
   Phase 4's deep-scan cache uses, reject with a comment reply rather than
   silent drop so the requester knows why nothing happened.

## What's explicitly not done

- App registration in the GitHub Developer settings UI (manual, one-time,
  needs a real `packagesafe` GitHub org).
- Private key storage/rotation strategy.
- The webhook route itself, JWT signing, and installation-token exchange code.
- Comment-formatting polish (collapsible `<details>` for large dependency
  lists, reacting to the triggering comment with 👀 while working).
- Deployment: needs a stable public HTTPS endpoint - the existing backend
  deployment target works once one exists; this phase didn't stand one up.

## Why this is last

Of the four surfaces, this is the only one that needs a live, publicly
reachable deployment *and* a registered GitHub App before anything can be
tested end-to-end - the other three (badge, Action, weekly report) are all
independently testable against a local backend, which is why they're built
first per the phase's own "highest-leverage first" instruction.
