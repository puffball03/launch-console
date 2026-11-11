# PR triage agent

`.github/workflows/pr-triage.yml` runs a Claude agent on every same-repo, non-draft PR (opened, reopened, ready for review, new commits).

```
gate ──► triage ──► merge     low risk → auto-merge once required checks pass
                ├─► fix       small problems → fix agent commits, push re-runs triage
                │              in re-review mode (merge or escalate only)
                └─► escalate  real risk → comment with recommended changes
```

The model proposes; the workflow decides. It can only make a decision more cautious:

| Guardrail | Effect |
|---|---|
| PR touches a path in `protected-paths.txt` (read from `main`) | always escalate |
| More than 300 changed lines | no auto-merge |
| Agent says `merge` at medium/high risk | escalate |
| Head commit is an agent fix (`Triage-Fix:` trailer) | re-review mode, no further fixes |
| 2 agent fix commits already on the PR | no further fixes |
| Fix touches protected paths, exceeds 80 lines, or tests fail | nothing pushed, escalate |
| Agent errors or returns no verdict | escalate |

Each outcome sets one label: `triage:auto-merge`, `triage:agent-fixed` or `triage:needs-human`.

## One-time setup

1. **Secrets** (Settings → Secrets and variables → Actions):
   - `CLAUDE_CODE_OAUTH_TOKEN`: runs the agent on your Claude Pro/Max subscription. Create it with `claude setup-token`. Runs share your plan's usage limits with your own Claude Code sessions; if a limit is hit mid-run, the PR is escalated. To bill API credits instead, swap `claude_code_oauth_token` for `anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}` in both Claude steps of the workflow.
   - `TRIAGE_BOT_TOKEN`: a fine-grained PAT for this repo with *Contents*, *Pull requests* and *Issues* set to read and write. Fix pushes and merges made with it trigger workflows, which is what makes the fresh re-review and CI on the fix commit happen. Without it, the agent still merges and escalates, but never fixes.

   To keep them in a local file: `cp .env.triage.example .env.triage`, fill it in, then `gh secret set -f .env.triage --repo puffball03/launch-console`. `.env.triage` is git- and Docker-ignored; keep it out of `.env`, which docker-compose loads into the app container.
2. **Settings → General → Allow auto-merge**: on.
3. **Branch protection on `main`**: require the `CI / test` status check. Auto-merge waits for it, so the agent can never merge a red PR.

Tune limits in the workflow's `env:` block and the protected list in `protected-paths.txt`.
