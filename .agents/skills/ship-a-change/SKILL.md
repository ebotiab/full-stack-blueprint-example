---
name: ship-a-change
description: Take a change in My Project from a branch to verified production — checks, pull request, auto-merge and the Logfire check after the deploy. Use it whenever a task is ready to become a pull request, or when asked to merge, deploy or check production.
---

# Ship a change

The rules behind each step are in `AGENTS.md` ("Before opening a pull request", "Conventions").
This is the order.

1. **Branch.** Work on a branch off an up-to-date `main`, one task per branch.
2. **API changed?** Run `make types` and keep the regenerated `backend/openapi.json` and `frontend/src/api/schema.d.ts`.
   Schema changed? A new migration file, never an edit of an applied one (`make migrate` applies it locally).
3. **Check.** `make fmt`, then `make check`. Fix until the summary says every step passed.
   Run it once, at the end, not after every edit.
4. **Commit and push.** One-sentence message describing the result. Lockfiles included when dependencies changed.
5. **Pull request.** `gh pr create` with a description that says what changes, why, what to look at
   in review and which checks passed. If the task closes an issue, add `Closes #N`.
6. **Merge on green.** When nothing is left to decide. `--auto` waits for the CI only if `main`
   requires its checks, and merging is deploying, so look first:
   `gh api 'repos/{owner}/{repo}/branches/main' --jq '.protection.required_status_checks.contexts'`
   - It lists `Backend` and `Frontend`: `gh pr merge --squash --auto`. If the CI fails, read the
     failing job (`gh run view --log-failed`), fix, push; the mark stays. If it answers "Pull
     request is in clean status", the CI already passed and there is nothing to wait for:
     `gh pr merge --squash`.
   - It does not (`main` is not protected yet): wait for the CI yourself,
     `gh pr checks --watch --fail-fast && gh pr merge --squash` (if it says no checks are reported
     yet, run it again in a moment), and tell the user to protect `main` (README, "Deploy").
7. **After the merge.** Update your local `main` (`git checkout main && git pull`). If the visor changed, open the production URL and look at the change.
8. **Production.** If `backend/` changed:
   `cd backend && uv run my-project obs status --commit <merge commit sha> --wait 15`.
   Done only when it exits 0 (the commit is deployed and has no errors). Exit 1: investigate the
   errors it lists before finishing. Exit 2: the deploy did not arrive; look at the platform's
   deploy log. Exit 3: there is no Logfire read token; tell the user and check by hand.
