# Phase 6: Portfolio Documentation and Version Control

This update prepares the working application for a portfolio review and a versioned source repository. It adds a current README, Windows setup, case study, demo walkthrough, GitHub instructions and expanded Git exclusions. It adds no application feature or migration.

## 1. Install the documentation update

Extract `MarginGuard_AI_Phase6_Update.zip`, open its inner `MarginGuard_AI_Phase6_Update` folder, and copy its contents into:

`C:\Users\apiyu\OneDrive\Lecture Notes\Application\MarginGuard AI`

Merge folders and replace the supplied files. If you added personal Git exclusion rules, retain them when merging `.gitignore`.

No database command, package installation or app restart is needed. The fresh-install Windows guide is for a separate empty installation; keep your current working data.

## 2. Review the portfolio material

- `README.md`: current project overview and documentation links.
- `docs/portfolio_case_study.md`: business problem, approach, results and limits.
- `docs/demo_walkthrough.md`: a four-minute presentation of the working application.

The financial benchmark is labelled as synthetic potential underbilling, rather than customer savings or collected cash.

## 3. Check Git

In your VS Code project terminal:

```powershell
git --version
git status
```

If `git status` reports that this is not a repository:

```powershell
git init -b main
```

For an existing repository, keep its current history and branch. Follow `docs/github_setup.md` to check exclusions, stage files and create the local milestone commit. Its later section explains how to connect a GitHub repository with your own account.

Git stores source and fictional fixtures. It does not back up PostgreSQL import batches, findings, notes or recovery history; that state needs a separate database backup.

## Verification

Documentation links and archive contents were checked. Git exclusions were checked in a temporary repository with dummy local configuration, cache, backup and export paths. Source modules, migrations, fictional fixtures and `.env.example` remain eligible for tracking.

No application code changed. The existing 80-test Phase 5 record remains the latest full application run; no new Windows or hosted verification is claimed by this documentation update.
