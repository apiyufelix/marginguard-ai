# MarginGuard AI — Reviewer Access

Open [the hosted demo](https://marginguard-ai-demo.streamlit.app/) and select **Sign in with Google**. This is a fictional-data portfolio demo maintained by Felix Apiyu.

## Request access

1. Sign in using your own Google account.
2. Copy the full **MarginGuard account ID** shown in the sidebar.
3. Send that ID to Felix through the channel where you received the invitation, asking for Viewer access.
4. After Felix confirms the grant, refresh the app.

Do not send a Google password, OAuth secret, cookie or database connection string. A MarginGuard account ID identifies an application account and is not a login credential.

Google sign-in and company membership are separate checks. A signed-in account without membership correctly sees no company dashboard. While the Google OAuth application remains in Testing, Felix must also add the intended account to Google's test-user list. A Google access-blocked screen occurs before the membership step.

## What a Viewer can do

View the company dashboard, filter investigations, inspect case evidence and activity, and download reports. Uploads, detection, case edits and membership administration require higher roles. Viewer access is the default reviewer role; Felix retains Admin access.

## Administrator handoff

Have the reviewer create their own hosted identity first. In the hosted **Company access** page, use their full hosted account ID, select **viewer**, enable **Membership active**, and save. Verify the displayed name/email as a cross-check; membership is bound to the account ID, not an email match. Never reuse a local database account ID for a hosted grant.

If Google blocks a testing account, add that intended account under the existing MarginGuard Google Auth Platform project's Audience test users, then have them sign in again. Do not promise unrestricted public signup while Testing is enabled.

To remove access, deactivate the membership. The reviewer should refresh to observe the denial. This controls application access; reports already downloaded remain with their recipient.

## Demonstration limits

All customers, orders, invoices and financial examples are fictional. Potential underbilling is a review candidate, confirmation is a reviewer decision, and recorded recovery is an application ledger entry rather than independently verified bank settlement. Explanations use deterministic rules; this version does not use an LLM. Access and availability are managed for demonstrations, not offered with a commercial service-level agreement.
