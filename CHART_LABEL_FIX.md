# Dashboard chart label fix

Install after Phase 5. Chart labels now put the customer/product ID before the display name, so labels shortened by the chart remain distinguishable. Full names and IDs remain in the tables below the charts.

1. Stop Streamlit with Ctrl+C.
2. Extract `MarginGuard_Chart_Label_Fix.zip` and copy the contents of the inner `MarginGuard_Chart_Label_Fix` folder into your existing MarginGuard AI project. Merge folders and replace `src/marginguard/dashboard_page.py`.
3. Restart from your project terminal:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open Dashboard → Exposure analysis. The customer bars should begin with distinct customer IDs. No database migration or package installation is required.

This is a display-only change; financial calculations, filters and case records use the existing services. Python syntax and archive contents were checked. The prior Phase 5 verification covers those services.
