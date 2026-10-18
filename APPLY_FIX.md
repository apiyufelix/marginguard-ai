# Evidence display fix

The calculation line now uses plain text so currency dollar signs are displayed literally. Financial calculations and database records are unchanged.

1. Stop Streamlit with Ctrl+C.
2. Extract the ZIP. Copy its src folder into your existing MarginGuard AI project, merging folders and replacing src/marginguard/cases_page.py.
3. Restart with .\.venv\Scripts\python.exe -m streamlit run app.py.

No database migration is required. The original demo seed has null source batch/row pointers because it predates the CSV upload workflow. Uploaded Phase 2 records such as IMP-IL001 have upload lineage.

Verified: Python compilation and the rendered Investigations page with a representative evidence snapshot; all currency symbols remain in the plain-text explanation.
