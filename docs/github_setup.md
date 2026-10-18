# Save and Publish with Git

Run these commands from the project root in VS Code's PowerShell terminal. Prepare a local commit first, then connect GitHub using your own account when ready.

## 1. Check the repository

```powershell
git --version
git status
```

If Git is unavailable, install Git for Windows and reopen the terminal. If this is not a repository:

```powershell
git init -b main
```

For an existing repository, keep its history and branch.

## 2. Check exclusions

The supplied `.gitignore` excludes local environment files, virtual environments, caches, backups, exports, download ZIPs and `data/uploads`. It retains `.env.example` and the fictional fixtures.

```powershell
git check-ignore .env .venv/ backups/ exports/
git status --short
```

The first command should list those ignored paths. Review any other files you placed in the project. Ignore patterns apply to matching untracked files; they do not untrack existing files.

For an existing repository, inspect tracked environment filenames:

```powershell
git ls-files -- .env '.env.*'
```

Only `.env.example` should appear. If `.env` was tracked, remove it from the index while keeping the local file:

```powershell
git rm --cached -- .env
```

Use the exact equivalent filename for another tracked local environment file. If credentials were already pushed, ignore rules do not remove old commits; replace those credentials and use GitHub's sensitive-data removal guidance.

## 3. Stage and inspect

```powershell
git add .
git status --short
git diff --cached --stat
```

Expect source, migrations, tests, docs, examples, project configuration and synthetic data. Local credentials, the virtual environment, database backups and exported reports should not be staged.

## 4. Commit the milestone

```powershell
git commit -m "Portfolio milestone: MarginGuard AI"
git status
```

If Git requests author identity, set it for this repository with your own email, then repeat the commit:

```powershell
git config user.name "Felix Apiyu"
git config user.email "YOUR_GIT_COMMIT_EMAIL"
```

Status should report a clean working tree when intended files have been committed. Git versions the source; it does not back up PostgreSQL case history.

## 5. Connect GitHub

Create an empty GitHub repository named `marginguard-ai`, choosing your intended visibility. Leave automatic README/license/gitignore initialization unchecked because these files already exist locally. Copy its HTTPS URL.

```powershell
git remote -v
```

If there is no `origin`, add the copied URL, replacing the example username:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/marginguard-ai.git
git remote -v
git branch --show-current
```

If origin already exists, verify its destination rather than automatically replacing it. Authenticate through the supported GitHub sign-in flow when prompted. For a branch named main:

```powershell
git push -u origin main
```

For another existing branch, substitute its actual name. Open the repository after pushing and check its rendered README and expected files.

## 6. Preserve database state separately

The repository can rebuild a fictional demo but does not contain PostgreSQL imports, cases, notes or recovery events. Use PostgreSQL/pgAdmin backup and restore for those records, storing backups outside tracked source. Check a restore in a separate database before relying on a backup.

## Official references

- [Adding local code to GitHub](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github?platform=windows)
- [Ignoring files](https://docs.github.com/en/get-started/git-basics/ignoring-files)
- [Removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
