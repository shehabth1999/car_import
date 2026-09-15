# car_import — deployment runbook

Everything in this folder is ready to install. Nothing here has been run against a
live database yet: the migration was generated offline and the workflow bundles
were built from the definition in code.

---

## 0. Before you start

| Need | Why |
|---|---|
| The module folder placed under a path in `EXTENSIONS_PATHS` | That is how the platform finds an external module (e.g. `E:\genie-erp\projects` or the server's equivalent) |
| `base`, `notifications`, `contacts`, `crm`, `dashboard`, `chat`, `whatsapp` installed | The manifest depends on them |
| **`sales`, `account`, `payment`, `products` NOT installed** | This project keeps accounting out; `check_ka_install` enforces it |
| A superuser to own the workflow | `build_ka_workflows` assigns one |

---

## 1. Install the module

```bash
uv run python manage.py install car_import
uv run python manage.py migrate car_import          # 4 tables: deal, stage, log, vehicle
uv run python manage.py sync_schema --status        # shows the partner/lead/ticket fields
uv run python manage.py sync_schema                 # apply them; a second run must say up to date
uv run python manage.py sync_all                    # views, menus, groups, permissions, actions
uv run python manage.py sync_tools --app car_import # registers the six AI tools
uv run python manage.py check_ka_install            # must print "clean"
```

Restart the Celery workers afterwards — stage messages and the AI run there, and each
worker holds its own copy of the code and the tool registry.

## 2. Seed the stages

```bash
uv run python manage.py seed_import_stages
```

Creates the client's 13 stages with the Arabic drafts and **customer messages switched
off**. Leave them off until Mr Khaled or the General Manager approves the wording and
WhatsApp approves the templates. Then:

```bash
uv run python manage.py seed_import_stages --enable-messages
```

## 3. Load the AI workflow

**Either** import the bundle through the UI — AI Studio → Workflows → Import → choose
`workflows/ka_sales_aya.bundle.json` (also `_ramy` and `_social`). Tools and models are
carried by name and resolved on this instance.

**Or** build it from code on the server:

```bash
uv run python manage.py build_ka_workflows --voice aya
```

Either way, open the agent node afterwards and confirm:

- the **model** and the **backup model** resolved (without a backup, a provider outage
  becomes the agent's reply text);
- all six tools are attached — if any is missing, run `sync_tools --app car_import` and
  rebuild;
- `error_message` is the Arabic hand-off sentence (the build command sets it; the bundle
  import does not carry it).

## 4. Connect a number, carefully

```bash
# 1. staff phones only
uv run python manage.py build_ka_workflows --voice aya --canary <partner_id> --canary <partner_id>

# 2. when it has been quiet for a week, the real number
uv run python manage.py build_ka_workflows --voice aya --release <whatsapp_account_id>

# panic button — humans take everything back
uv run python manage.py build_ka_workflows --rollback
```

Check the tenant's AI quota before releasing (`ai.monthly_contact_limit`, `ai.paid_until`):
past the limit the agent simply stops replying, with nothing in the conversation to show why.

## 5. Migrating the open deals

Import them with **`notifications_suppressed` on**, so nobody is messaged about a stage
they reached weeks ago. Switch it off per deal as each customer is confirmed — the next
real stage move is then their first automatic message.

---

## What this release does

- The deal (`CarDeal`), the 13 stages, the change log and the car record.
- Every stage move logs and messages the customer — inside WhatsApp's 24-hour window as
  text, outside it as an approved template, on any other channel through the universal
  sender. A failure raises an activity for the agent instead of disappearing.
- Deal pipeline, form, list and search; car, stage and message-log screens.
- Identity fields on the contact, qualification on the lead, **Create car deal** on the lead.
- Six security groups and the install guard.
- An AI agent for WhatsApp/Messenger/Instagram/TikTok/web chat with six tools:
  deal status, send status, eligibility, instalment terms, fees, and hand-off to a human.

## What it deliberately does not do yet

| Not built | Why / what unblocks it |
|---|---|
| Price quotes and the deposit tables | The loader needs the fee schedule and the down-payment calculator from the client |
| mobile.de search | The account questions came back blank; Mr Khaled holds the account |
| Contract generation | Needs the blank templates and the instalment wording from their lawyer |
| Documents / KYC lane (vision) | Second AI lane; comes after the document checklist |
| Website tracking-page feed | Waiting on an introduction to their engineer, Ahmed Saeed |
| Call summaries from Dropbox | Separate module, `car_call_summary` |
| Out-of-hours AI after 30 minutes of agent silence | Lives in the inbound path, not in this graph |

## Rules encoded here, so nobody has to remember them

- Instalments are refused when the customer holds the initiative himself.
- Any 3 of the 6 options put a car in the full deposit tier.
- The AI never states a down-payment percentage, never sends an account number, never
  confirms a transfer, and never computes an instalment amount.
- Cancellation never messages the customer automatically.
- The licence cost is never quoted; the licensing service fee is 3,000 EGP.
