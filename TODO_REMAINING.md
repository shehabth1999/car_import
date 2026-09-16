# car_import — what is left, as a list you can tick

Kept untracked on purpose: it is a working list, not part of the module.
Updated 2026-09-16. **~21 of 64 days done · ~43 left.**

Legend: 🔴 nothing blocking it · 🟡 waiting on the client · ☐ not started · ☑ done

---

## Slice A — call summaries (5 d) 🔴 — *the client's stated priority #3*

- ☐ A1 `CallRecording` model — Dropbox file id, path, recorded at, agent, customer phone, audio, transcript, summary, action items, match state
- ☐ A2 `dropbox_sync` service — refresh-token auth, `files/list_folder` + `/continue` with a stored cursor, dedupe by Dropbox file id
- ☐ A3 Simulated backend, same pattern as mobile.de, so it runs before the Dropbox app exists
- ☐ A4 Matching — phone number from the file name, the agent from the folder, the call time; anything ambiguous goes to a review list instead of a guess
- ☐ A5 Transcription + Arabic summary + action items onto the deal's chatter
- ☐ A6 Screens, menu, permissions, nightly job
- ☐ A7 Config: which folder, which agents, retention

## Slice B — evals (2 d) 🔴

- ☐ B1 Golden dataset from the four demo conversations plus every defect found so far
- ☐ B2 Assertions: no invented figure, no bank details, escalation where required, Arabic only
- ☐ B3 Point it at a dedicated internal contact — eval runs are NOT sandboxed and side-effecting tools fire for real
- ☐ B4 Run it against Haiku and record the baseline

## Slice C — showroom and initiative listings (4 d) 🔴

- ☐ C1 `ShowroomListing` — a car already in Egypt: EGP price, licensed, protection film, published to the website
- ☐ C2 `InitiativeListing` — holders selling a deposit right, with buyer matching
- ☐ C3 Screens, menus, permissions
- ☐ C4 `ka_search_initiative_listings` + `ka_register_initiative_for_sale` (agent A7)

## Slice D — the rest of the AI layer (8 d) 🔴

- ☐ D1 `ka_search_vehicle_listings` — the mobile.de search as a tool
- ☐ D2 A5 follow-up cadence: nudge, then close as lost with a reason
- ☐ D3 A4 documents lane with vision — receive a photo, file it against the right requirement
- ☐ D4 RAG collection from the approved company answers + FAQ
- ☐ D5 A10 supervisor: sample replies, flag invented figures and promised dates
- ☐ D6 `ramy` and `social` workflows built and verified alongside `aya`

## Slice E — management sight (8 d) 🔴

- ☐ E1 Deal dashboard: pipeline by stage, stuck deals, unpaid marks, message delivery
- ☐ E2 CRM dashboard: funnel by source and agent, response time, win rate
- ☐ E3 Follow-up cadence rules (`FollowupRule`) wired to the documented nudge sequence
- ☐ E4 Lead intake from ads and click-to-WhatsApp, with campaign attribution
- ☐ E5 Install the remaining channel modules: messenger, instagram, tiktok, webbot, support
- ☐ E6 Companies and branches — K&T, the GmbH, the showroom

## Slice F — operational hygiene (3 d) 🔴

- ☐ F1 Put real users into the six car_import groups — **the access rules apply to nobody until this is done**
- ☐ F2 Migration runbook for the open deals, with `notifications_suppressed` on
- ☐ F3 Contact and lead import, deduplicated by phone
- ☐ F4 Delete the demo customers and deals before handover

---

## Waiting on the client — do not start

- 🟡 Pricing engine, down-payment calculator, `Quote`/`QuoteLine`, the offer PDF, agent A2 (12 d) — needs the fee schedule as one dated document and the calculator formula
- 🟡 Contracts: `contract_render`, `GeneratedDocument`, `ContractIssuer`, `ContractPaymentLine` (13 d) — needs the lawyer's templates. **The Arabic RTL PDF spike (1.5 d) can start now**
- 🟡 mobile.de going live — the API request is with them; the code is finished and running simulated
- 🟡 Stage messages going live — wording approval, then Meta template approval (days)
- 🟡 Website tracking feed — their engineer, Ahmed Saeed
- 🟡 The AI provider key on the client's own account

---

## Decisions still open

- 🟡 May the assistant state the published fees? (`car_import.ai_may_quote_published_fees`, default off)
- 🟡 Is the customs figure the amount payable, or the value the rate applies to? (question V1) — the pricing engine refuses until answered
- 🟡 Korea: the company's own Q&A says yes, the owner's answer says Europe only
- 🟡 The 15/80/20 booking schedule contradicts the calculator answer
