# Phase 10 — Portfolio documentation update

Copy README.md and the three docs/ files from this update into the existing MarginGuard AI project, replacing those same files. Add PHASE10_SETUP.md at the project root. This update changes documentation only; it does not alter the database, login configuration or application behavior.

Review the live link and rendered Markdown in VS Code. Follow docs/demo_walkthrough.md for the presentation and screenshot capture. Images must come from the working application and be reviewed before publication; this update does not contain screenshots.

From the project root in PowerShell:

```powershell
git switch -c docs/portfolio-demo
git diff --check
git add README.md docs/demo_walkthrough.md docs/portfolio_case_study.md docs/reviewer_access.md PHASE10_SETUP.md
git commit -m "Document hosted demo and portfolio walkthrough"
git push -u origin docs/portfolio-demo
```

Open a pull request to main and wait for both CI checks before merging. Application tests are unchanged; no additional tests are introduced for this documentation update. After merging, switch to main and pull with --ff-only.
