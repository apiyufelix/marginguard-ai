"""Run the full suite for CI, refusing missing database configuration or skips.

Use MARGINGUARD_TEST_DATABASE_URL for a disposable PostgreSQL database.
The normal local unittest command remains available without integration tests.
"""
from pathlib import Path
import os
import sys
import unittest


def main():
    if not os.environ.get('MARGINGUARD_TEST_DATABASE_URL', '').strip():
        print('CI requires MARGINGUARD_TEST_DATABASE_URL for a disposable PostgreSQL database.', file=sys.stderr)
        return 2

    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    suite = unittest.defaultTestLoader.discover(str(root / 'tests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun == 0:
        print('CI failed: no tests were discovered.', file=sys.stderr)
        return 1
    if result.skipped:
        print(f'CI failed: {len(result.skipped)} tests were skipped; complete database coverage is required.', file=sys.stderr)
        return 1
    if not result.wasSuccessful():
        return 1
    print(f'CI verification passed: {result.testsRun} tests, no skips.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
