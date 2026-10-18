# Add portfolio screenshots

Copy README.md and docs/screenshots/ from this ZIP into the existing MarginGuard AI project. The four PNG files are unchanged copies of the reviewed application captures. No application code or database changes are included.

After the earlier documentation pull request is merged, run from the project root:

```powershell
git switch main
git pull --ff-only origin main
git switch -c docs/demo-screenshots
```

Copy the update files, preview README.md with Ctrl+Shift+V and check that all four images render. Then:

```powershell
git diff --check
git add README.md docs/screenshots PHASE10_SCREENSHOTS_SETUP.md
git commit -m "Add hosted demo screenshots to portfolio README"
git push -u origin docs/demo-screenshots
```

Open a pull request into main. Wait for both existing CI checks before merging. Documentation/image changes introduce no new tests. Keep a clean main checkout after merging by switching to main and pulling with --ff-only.
