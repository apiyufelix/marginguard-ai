# Phase 7: Automated Tests on GitHub

This update adds a GitHub Actions workflow, a strict CI test runner and CI documentation. The workflow runs Python 3.12 and 3.13 jobs, each with a disposable PostgreSQL 16 service. No local database migration or new application package is required.

## 1. Copy the update

Extract `MarginGuard_AI_Phase7_Update.zip`, open its inner `MarginGuard_AI_Phase7_Update` folder, and copy all its contents into your existing project:

`C:\Users\apiyu\OneDrive\Lecture Notes\Application\MarginGuard AI`

Merge folders and replace matching files. Include the `.github` folder; it contains `.github/workflows/tests.yml`. The five supplied files are the workflow, `scripts/run_ci_tests.py`, `docs/ci.md`, this setup guide and the updated README.

Your running Streamlit app can remain open. These changes configure testing rather than application behavior.

## 2. Commit and push

From the VS Code project terminal:

```powershell
git add .github/workflows/tests.yml scripts/run_ci_tests.py docs/ci.md PHASE7_SETUP.md README.md
git diff --cached --stat
git commit -m "Add Python and PostgreSQL CI checks"
git push
```

The stat should list those five files. The existing upstream connection to `apiyufelix/marginguard-ai` lets `git push` use `origin/main`.

## 3. Watch the first run

Open your GitHub repository and select **Actions**, then the **Tests** workflow and its most recent run. Both jobs should complete successfully:

- Python 3.12 / PostgreSQL 16
- Python 3.13 / PostgreSQL 16

Open each job's **Run unit and PostgreSQL integration tests** step. For the current application, expect **80 tests**, no skips, and a final message:

```text
CI verification passed: 80 tests, no skips.
```

The hosted run is the confirmation for GitHub's runner, native PostgreSQL service and both Python versions. Local preparation alone does not establish that hosted result.

## 4. Understand the difference from the local check

Your normal local command still works:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Without a test database setting, that command passes 59 tests and skips 21 optional integration tests. CI supplies its own test database and treats any skipped test as a failure. Do not run the strict CI script against your application's working database; its integration tests create and drop isolated test schemas in the disposable database.

No GitHub secret or local PostgreSQL password is needed for this workflow. The password in the YAML belongs only to the fresh test service inside the job.

## 5. If a job fails

Open the failed step and share the error text or screenshot. An installation failure, service startup problem or application test failure needs a different fix, so use the first relevant error from that step. The workflow does not change your Windows database or deploy the application.

After both jobs are green, the next development stage can add verified login and organization access controls, then prepare a hosted demonstration.
