# Phase 8B — test Google sign-in

This is a standalone login check. `app.py` is unchanged and has no login gate or
role enforcement yet. This page does not connect to PostgreSQL, provision users,
assign roles, or expose company data. Keep using local development while we build
the authenticated application in the next step.

1. Extract this update into the existing project root. Keep your private
   `.streamlit/secrets.toml` in place. Stop any running Streamlit process.
2. The previous terminal screenshot showed the generated cookie secret. Replace
   just its value with a fresh random string. This PowerShell command puts the
   fresh value directly on the Windows clipboard without printing it:

   ```powershell
   .\.venv\Scripts\python.exe -c "import secrets,subprocess; subprocess.run(['clip.exe'], input=secrets.token_hex(32), text=True, check=True)"
   ```

   Paste inside the quotes for `cookie_secret` in `.streamlit/secrets.toml` and save.
   Keep the current Google client ID and newly saved client secret unchanged.
3. Install dependencies from the project root:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

4. Run the standalone page on the callback's configured port:

   ```powershell
   .\.venv\Scripts\python.exe -m streamlit run login_check.py --server.address localhost --server.port 8501
   ```

5. Open `http://localhost:8501`, select **Sign in with Google**, and use your
   Google test account. Expect **Google sign-in succeeded.** and your display name.
   Select **Sign out** and verify the sign-in button returns.

The redirect URI in both Google Cloud and `.streamlit/secrets.toml` must be exactly
`http://localhost:8501/oauth2callback`. Use plain URLs in TOML. Check that your
Google account is listed under Audience / Test users while the client is Testing.
If port 8501 is occupied, stop the previous Streamlit process rather than using a
different port without updating both callback settings.

Return only whether sign-in and sign-out worked, or the error wording. Do not
share secrets, full identity claims, credentials JSON, or callback URL query strings.

Reference: https://docs.streamlit.io/develop/tutorials/authentication/google

Local validation checked both page states and button callbacks with Streamlit
AppTest and mocked identities. It did not execute Google's real browser flow;
that end-to-end check happens on your local machine with your credentials.
