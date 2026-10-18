# Continuous Integration

## Configuration

The `Tests` workflow runs for pushes to `main`, pull requests targeting `main`, and manual dispatch. Its matrix uses Python 3.12 and 3.13 on Ubuntu. Each job starts a separate PostgreSQL 16 service, waits for its health check, installs runtime requirements and the editable project, then calls `scripts/run_ci_tests.py`.

The service uses a disposable `marginguard_ci` database. `MARGINGUARD_TEST_DATABASE_URL` points to that job's loopback port and test-only credentials. The workflow does not read the developer's `.env` or use a production database connection. Existing integration tests create and drop randomly named schemas in the supplied test database.

The workflow grants repository-content read permission and disables checkout credential persistence. It installs no deployment credentials and performs no publication or application deployment. Each matrix job has a 15-minute timeout. The checkout and setup-python actions use their v6 major tags; application dependencies retain the project's existing compatibility ranges rather than an exact lockfile.

## Strict test gate

The strict runner:

1. Requires an explicit nonblank test database environment variable before discovery.
2. Runs the existing unittest suite from the project root.
3. Fails on test errors/failures, any skipped tests, or empty discovery.
4. Prints its no-skips success message only after all checks succeed.

It does not hardcode a test count, so additional tests can be added normally. At this milestone, the suite has 80 tests: 59 unit/fixture tests and 21 database integration tests. The optional local unittest command retains its existing skip behavior.

## Coverage and limits

The suite covers financial rules, synthetic fixture truth, CSV validation and relational imports, transactional case actions, recovery corrections, report serialization and pure dashboard analytics. Database tests include tenant-scoped queries, stale versions, append-only events and rollback. This workflow does not currently run the separate development Streamlit AppTest harness, browser pixel checks, production load or deployed identity/authorization tests.

The workflow should be confirmed in GitHub after the first push. A locally validated YAML file is not evidence of a successful hosted job. Two successful matrix jobs establish the actual hosted Python/PostgreSQL result for that commit. Passing this workflow also does not create branch-protection rules; required checks would be configured separately if desired.

## Local preparation verification

The workflow YAML and its matrix, service, environment and step references were checked. The strict runner was checked for missing configuration, skipped tests and empty discovery. The complete existing 80-test suite passed through this runner using the development embedded PostgreSQL adapter with no skips.

Native PostgreSQL and Docker executables were unavailable in the authoring environment. The GitHub-hosted PostgreSQL 16 and Python 3.13 results therefore remain pending the first workflow run. No new application or schema change is included in this phase.

## Official references

- [GitHub: building and testing Python](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)
- [GitHub: PostgreSQL service containers](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers)
