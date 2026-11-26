---
name: ship-a-change
description: >-
  Take a change in My Project from a branch to verified production — checks, pull request, auto-merge and the Logfire check after the deploy. Use it whenever a task is ready to become a pull request, or when asked to merge, deploy or check production.
---

# Ship a change

The rules behind each step are in `AGENTS.md` ("Before opening a pull request", "Conventions").
This is the order.

1. **Branch.** Work on a branch off an up-to-date `main`, one task per branch.
2. **API changed?** Run `make types` and keep the regenerated `backend/openapi.json` and `frontend/src/api/schema.d.ts`.
   Schema changed? A new migration file, never an edit of an applied one (`make migrate` applies it locally).
3. **Check.** `make fmt`, then `make check`. Fix until the summary says every step passed.
   Run it once, at the end, not after every edit.
4. **Commit and push.** Follow `AGENTS.md`, "Commit style": `commit_style=gitmoji`,
   one Unicode emoji, a space and an English imperative summary
   (for example, `🐛 Reject expired sessions`). Include lockfiles when dependencies changed.
5. **Pull request.** `gh pr create` with a description that says what changes, why, what to look at
   in review and which checks passed. The title uses the same commit style and summarizes the
   whole change. If the task closes an issue, add `Closes #N`.
6. **Merge on green.** When nothing is left to decide. `--auto` waits for the CI only if `main`
   requires its checks, and merging is deploying. First normalize the final PR title to the
   selected style, including bot PRs, then read `pr_title=$(gh pr view --json title --jq .title)`.
   Pass it explicitly as the squash subject: GitHub's default can use an individual commit's
   subject instead of the PR title. If the title changes after scheduling auto-merge, refresh
   the scheduled subject too. Check protection:
   `gh api 'repos/{owner}/{repo}/branches/main' --jq '.protection.required_status_checks.contexts'`
   - It lists `Backend` and `Frontend`: `gh pr merge --squash --auto --subject "$pr_title"`. If the CI fails, read the
     failing job (`gh run view --log-failed`), fix, push; the mark stays. If it answers "Pull
     request is in clean status", the CI already passed and there is nothing to wait for:
     `gh pr merge --squash --subject "$pr_title"`.
   - It does not (`main` is not protected yet): wait for the CI yourself,
     `gh pr checks --watch --fail-fast && gh pr merge --squash --subject "$pr_title"` (if it says no checks are reported
     yet, run it again in a moment), and tell the user to protect `main` (README, "Deploy").
7. **After the merge.** Update your local `main` (`git checkout main && git pull`).
   Read the PR's merge SHA (`gh pr view <number> --json mergeCommit --jq .mergeCommit.oid`) and
   inspect `git show -s --format=%s <merge-sha>`: it must keep the selected style and final PR title
   (a PR number suffix is fine). Report a mismatch; never rewrite published history to fix style. If the visor changed, open the production URL and look at the change.
8. **Production.** If `backend/` changed:
   `cd backend && uv run my-project obs status --commit <merge commit sha> --wait 15`.
   Done only when it exits 0 (the commit is deployed and has no errors). Exit 1: investigate the
   errors it lists before finishing. Exit 2: the deploy did not arrive; look at the platform's
   deploy log. Exit 3: there is no Logfire read token; tell the user and check by hand.
