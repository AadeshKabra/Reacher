# Learning Progress

## 2026-11-21 — Query flow walkthrough and /enrich fix
- Explained (by AI, not yet learner-demonstrated): end-to-end /processQuery flow, the find_leads pipeline, and how all LLM calls route through the Claude Code CLI subprocess.
- Implemented before learning mode was re-activated: /enrich passed an undefined `browser`; changed to `pipeline.browser` (Backend/app.py, enrich_contacts). The design choice was AI-proposed and user-approved ("Yes, fix it"), with no learner reasoning recorded. Compile-checked only; endpoint not exercised. Not committed as of this entry.

## 2026-11-21 — Pending: chat input bar position (UI)
- Requirement (learner): after the first query, the input bar should move down; currently it stays mid-page.
- Learner: bar should stick to the bottom of the window. Observed: bar does move down, but there is extra space below it, and submitting auto-scrolls the window.
- Explained: scrollIntoView scrolls every scrollable ancestor, including the window; `.app-layout` hardcodes the nav height as 65px.
- New symptom (learner): lead cards show below the input bar. Explained: sticky `bottom: 0` pins to the bottom of the scroll container (`main`), not the window.
- Measured in browser (768px viewport): body margin 8px, nav 75px (not 65), .app-layout 703px → stack 786px, so main/bar end 18px below the window. ChatHistory sidebar is 768px tall starting at y=83 → document 851px, window scrolls 83px. After the window scrolls, the bar's bottom is at 703 with a 65px gap below. Card-below-bar case not reproduced (saved chats load without leads).
- Learner design (confirmed, implemented): body margin 0; #app as flex column; layout fills the rest; sidebar height 100%. Learner identified #app as the column and the sidebar fix after one prompt about the second overflow source. Added on AI proposal (approved): #app height 100vh, .app-layout min-height 0.
- Verified in browser: document height = viewport (768), nav 75, layout/main/sidebar 693, window no longer scrolls, bar bottom = 768.
- Found (pre-existing, separate): `.chat` has flex: 1 + min-height: 0, so it shrinks to fit `main` and long content overflows its box; the bar's normal position sits right after the shrunk `.chat`, so with long content it scrolls out of view (probe test: bar top -1848 with main scrolled to the bottom). Likely cause of cards appearing below the bar.
- Learner design (confirmed, implemented): remove `min-height: 0` from `.chat` so it grows with its messages. The learner's reasoning connected the shrink to the bar's natural position without further prompting.
- Verified in browser (30 probe blocks, animations finished): bar bottom = 768 at the top, middle and bottom of the scroll; the last message ends above the bar; document height = viewport. Not tested with a live query's real lead cards.
- Status: input bar UI fixes done and confirmed working by the learner; not committed. Next: memory pipeline design (learner owns the design).

## 2026-11-21 — Pending: chat message alignment and lead card source link
- Learner requirements: user messages align right; remove the Source button and highlight the lead's name when the card is hovered.
- Open questions put to the learner: what clicking the name/card does (source_url access), touch/keyboard discoverability, whether the Email button stays. Flagged: in COMPANY mode the card shows "@ <location/stage>" because the synthesizer puts location/stage in `company`.
- Implemented (learner-authorized): `.message.user` align-self flex-start → flex-end. Verified in browser: user message flush right. Side effect flagged: plain-text assistant messages (`.message.assistant`) were already flex-end, so both sides are now on the right; learner to decide.
- Learner dropped hover-only idea (touch concern); real goal is uniform card layout. Asked for options → offered (AI proposals): pin actions to the card bottom, clamp relevance text, clamp title/subtitle. Decision is the learner's.
- Learner decisions (implemented): assistant plain-text replies align left; pin card action buttons to the card bottom (chosen from offered options; no clamping).
- Implemented: `.message.assistant` → flex-start; `.lead-info` flex column; `.lead-actions` margin-top: auto. Verified with injected probe cards: buttons in the same row share a bottom edge (569/569); user right, assistant left.
- Open: company-mode "@" field bug (unanswered twice — don't re-ask unless learner raises it).

## 2026-11-21 — Pending: landing page layout (hero on top, fit without scrolling)
- Learner requirement: move the hero ("Find people. Reach Out.") to the top; shrink the resume dropzone if needed so the landing fits on one screen.
- Measured at 768px window: main 693px tall, landing content 964px → 271px over. Breakdown: main top padding 56, upload section 258 (zone padding 48px top/bottom), search-section margin 56 + 181, hero margin-top 100 + 297 (64px padding top/bottom).
- Explained: moving the hero alone saves nothing; shrinking only the dropzone can't cover 271px.
- Learner decisions (implemented): target 768px; hero at top; cut hero margin/padding; shrink dropzone padding. AI additions (approved): section gap 56→40, removed hero divider line, fade-in order hero→upload→search.
- Implemented: hero margin 0, padding 0 0 24px; dropzone padding 20px 32px; .section-gap 40px.
- Verified at 768px: main content 693/693 (no scroll), search section ends at 747 with 21px spare. Not checked at phone widths.
- Status: done; not committed.

## 2026-11-21 — Frontend critique + accessibility audit (findings only)
- Ran Impeccable critique (dual-agent): 15/40 (Poor). P0: /chats has no auth (any user_id readable); mobile layout unusable (main 94px at 375px). P1: keyboard/screen-reader gaps (div/span controls, unlabeled inputs, no aria-live, invisible focus ring, lang=""); undesigned 1–2 min wait. P2: results not the visual hero. Bug: handleDrop never uploads.
- Explained (AI): frontend quality factors beyond looks (a11y, responsive, states, feedback, consistency, copy, performance, motion, security, trust).
- Snapshot: .impeccable/critique/2026-11-21T17-50-30Z__frontend-vue-project-src-components-home-vue.md
- Learner choices: fix chat privacy (/chats) first; wants a more distinct visual identity (bigger redesign, later); one issue at a time.
- Explained: identity today is the email from the OAuth redirect URL, stored in localStorage and sent as user_id; the backend has no session, so it can't verify who is asking.
- Learner learned/asked: how sites verify users, sessions vs tokens, where OAuth fits (explained: OAuth verifies once at callback; app then issues its own proof).
- Learner decisions: JWT (reason: avoid a per-request DB lookup — feedback given that the lookup is ms vs 30–120 s searches, JWT still fine and simpler); HttpOnly cookie (asked for a suggestion; picked the recommended option); 7-day expiry; require login to search (asked for a recommendation; picked it).
- AI additions (approved via plan): PyJWT HS256, JWT_SECRET in Backend/.env (startup fails without it), SameSite=Lax cookie, /me, /logout, 404 for non-owners, ownership check before running a query on an existing session_id.
- Implemented: app.py create_token/get_current_user/me/logout; callback sets the cookie and no longer puts name/email in the URL; /chats, /chat/{id}, /enrich/{id}, /uploadResume, /processQuery use Depends(get_current_user). Home.vue: credentials include, /me on load, localStorage identity removed, sign-in prompt when logged out or 401. ChatHistory.vue: /chats without user_id, refetch/clear on user change.
- Verified (test copy on :8001): no/forged/expired token → 401 on all routes incl. ?user_id=; valid token /me 200; /chats returns only the caller's chats; another user's chat → 404. Browser: logged-out page calls only /me, sidebar empty, search shows the sign-in prompt and sends no request.
- Not verified: real Google sign-in round trip (needs the :8000 backend restarted and the learner to sign in). PyJWT is in Backend/venv; also installed into system Python by mistake (harmless).
- Noted for later: REQUEST_TIMEOUT_MS = 30 s also applies to /processQuery, which usually takes longer.
- Learner confirmed: login + new chat work logged in and logged out; cookie visible in DevTools; URL no longer carries email.

## 2026-11-21 — Per-login OAuth state
- Learner asked how the JWT is verified (explained: HMAC signature recomputed with JWT_SECRET, plus exp; the payload is readable but not changeable; cookie storage vs localStorage corrected) and why state must be per-login (learner's own intuition: independent values per session).
- Learner decision: short-lived HttpOnly `oauth_state` cookie. AI additions (approved): 10 min, path /callback, SameSite=Lax, constant-time compare, deleted on every /callback response, global dict removed.
- Implemented in app.py (google_login sets the cookie; callback compares and clears it via _clear_oauth_state).
- Verified on :8001: cookie flags correct; cookie value equals the state sent to Google; no or wrong cookie → 400 and cleared; non-ASCII state → 400; matching cookie passes the check; two overlapping logins get separate states and A stays valid after B starts. Real Google round trip left to the learner (restarting :8000 themselves). Relevant code: Home.vue `.search-fixed` (margin-top: auto; position: sticky; bottom: 0), `main` (flex column, overflow-y: auto), `.chat` (flex: 1).

## 2026-11-21 — Idea: user memory pipeline (deferred until after UI fixes)
- Requirement (learner): store valuable context from user-provided files/data and use it to tune results.
- Explained: existing resume_profile is a single-source, fixed-schema version of this. Open design questions left to the learner: what to store, sources, where it's used, updates, trust boundary.
- Learner proposal (not yet confirmed): store resume info, query history/types, background inferred from queries, and intent preferences (jobs, networking, mentorship); derive from files and queries. Unsure how to resolve conflicts; wants prompt-injection guardrails without finetuning.
- Explained: provenance/recency/confidence as conflict-resolution inputs; injection defenses outside the model (data delimiting, no tools on the CLI, schema validation, capped structured memory writes, separating memory writes from actions); memory poisoning as a persistent risk.
