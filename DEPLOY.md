# car_import — deployment runbook

**Installed and exercised on `khaled_test` (khaled-test.genie-erp.com) on 2026-09-15.**
Everything below has now been run against a real database, not just written down.
What that run found is in "What the first install taught us" at the end — read it
before doing this on a second tenant.

---

## 0. Before you start

| Need | Why |
|---|---|
| **This repo pushed to a remote the server can pull** | ⚠ `genie-ops <slug> update` and converge run `git reset --hard origin/main` inside every extension repo, with no dirty guard. Anything only committed locally is erased on the next deploy |
| **The deployment's `extensions_repo_url` set on central** | One repo per deployment (`models_fleet.py:573`). If the tenant already points at another extension, pointing it here **removes that one** on the next converge. Central also only writes `EXTENSIONS_PATHS` into the tenant's `.env` when this field is non-empty (`provisioning_service.py:405`) — with it blank, the folder can be on disk and the app will never look at it |
| `base`, `notifications`, `contacts`, `crm`, `dashboard`, `chat`, `whatsapp` installed | The manifest depends on them |
| **`sales`, `account`, `payment`, `products` NOT installed** | This project keeps accounting out; `check_ka_install` enforces it |
| A superuser to own the workflow | `build_ka_workflows` assigns one |
| **An API key on the AI provider the agent uses** | On `khaled_test` every `LLMProvider` row had `api_key` empty, so the agent answered "Anthropic authentication failed" instead of the customer. The backup model does not save you: it was configured, and its provider had no key either. Set the key in AI Studio → Providers, or through the deployment's environment on central, **before** any canary |

---

## 1. Install the module

Take a baseline first — a `genie-ops <slug> backup`, `free -m`, `df -h`,
`manage.py sync_schema --status` — and run one `manage.py` process at a time.

**Getting the code onto the tenant, without a converge.** A converge is fifteen
phases long and rebuilds the frontend; none of that is needed to add an
extension. The narrow path, which is what was actually used:

```python
# on central, as the central app user
d = Deployment.objects.get(slug='<slug>')
d.extensions_repo_url = 'https://github.com/shehabth1999/car_import.git'
d.extensions_branch = 'main'
d.save()
ProvisioningService.push_env(d)      # rewrites .env, restarts the four units
```

Before that push, diff the rendered `.env` against the live one — `push_env`
rewrites the WHOLE file from the row, so any key hand-added on the host is lost.
On `khaled_test` the two were identical and the push added exactly one line.

Then clone the repo on the tenant host, as the tenant's own user, into a folder
named after the **package**, not the repository:

```bash
sudo -n install -d -o genie_<slug> -g genie_<slug> -m 750 /srv/genie/<slug>/extensions
sudo -n -u genie_<slug> bash -lc "cd /srv/genie/<slug> && \
    git clone --branch main https://github.com/shehabth1999/car_import.git extensions/car_import"
```

A later converge finds this checkout by its remote URL and just fetches into it.

```bash
uv run python manage.py load_apps                               # the manifest must be a base_module row first
uv run python manage.py install car_import                      # migrates the 4 tables AND adds the extension fields
uv run python manage.py showmigrations car_import               # 0001, 0002 both [X]
uv run python manage.py sync_schema --status                    # nothing pending FOR car_import
uv run python manage.py sync_all                                # views, menus, groups, permissions, actions, tools
uv run python manage.py sync_access_conditions                  # ⚠ sync_all does NOT do this
uv run python manage.py setup_car_import_org --report           # groups must not be empty
uv run python manage.py check_ka_install                        # must print "clean"
```

`install` does more than the name suggests: it adds the app to `INSTALLED_APPS`
for its own process, migrates, and applies the model extensions — on
`khaled_test` that was 4 tables plus 21 fields on the contact and the lead, in
one command. A separate `sync_schema --from-module car_import` is belt and
braces; run it if `--status` still lists car_import.

**Two commands `sync_all` will not run for you.**

`sync_all` has its access-conditions step commented out (`sync_all.py:127`), so
the row-level rules — the ones the brief makes a contractual obligation — deploy
as dead code until `sync_access_conditions` is run explicitly. It was found that
way on the first tenant: the rules were in the repo, on the server, and not in
the database.

And a security model needs people in it. `setup_car_import_org --report` names
every empty group, because six groups with nobody in them means every permission
and every access rule applies to nobody. Assign with
`--assign person@example.com=sales_agent`, and `--branches` creates K&T, the
GmbH and the showroom against the tenant's existing company.

`sync_schema --status` will very likely report **one** pending change that is
not ours (`contenttypes.contenttype.name` from `modules.base`). It was pending
before this module arrived. Leave it alone.

Then restart the services, in this order: **Celery worker → gunicorn reload (HUP) →
daphne**. Stage messages, the AI and the tool registry all live in the worker, and each
worker process keeps its own copy until it restarts.

Never run `sync_ui_views --app car_import` — the `--app` form deletes view rows. Use the
global `sync_all`.

**Later updates** to this extension (after the first install) are simply:

```bash
# on your machine: commit AND push first, or the deploy will wipe the change
uv run python manage.py sync_schema --from-module car_import
uv run python manage.py migrate car_import
# restart worker → gunicorn reload → daphne → sync_all
```

or let the fleet do it: `genie-ops <slug> update`, which runs migrate → deploy_sync
(sync_schema, sync_all, collectstatic) → a graceful service swap under a lock. If an
update fails part-way it can leave `.maintenance` behind and nginx keeps serving 503 —
check for that file after any failure.

## 1b. Seed the data the module runs on

Three commands, in this order. The first two are not optional — the module
answers customers out of these tables.

```bash
uv run python manage.py seed_reference_data        # programmes, tax bands, fees, financing, EUR 1
uv run python manage.py seed_import_stages         # the 14 stages + the deal number sequence
uv run python manage.py schedule_car_import_jobs   # the three recurring jobs
```

`seed_reference_data` writes only what the owner confirmed, and prints what it
is deliberately NOT writing — whether the customs figure is payable or a
valuation, and bank financing terms. An empty table makes the pricing engine
refuse; a plausible wrong number makes it quote confidently and be wrong by a
factor.

It also writes the **five pricing bands and the seven calculator fees** taken
from the client's own `New Quotation.xlsx`. Prove they landed correctly before
anyone quotes from them:

```bash
uv run python manage.py price_car --check
```

That replays the workbook's two worked examples — 48,001 € from the English
sheet and 30,000 € from the Arabic one — against the values cached inside the
file itself, and fails loudly if this engine and the client's calculator
disagree by a cent. It also asserts that a fully loaded quote's rows add up to
its own total, which the workbook cannot test because the workbook has no
discount. Run it after any change to a band or a fee.

To price one car without creating a quotation:

```bash
uv run python manage.py price_car 48001 --eur1 --shipping container --port port_said --paid 20000
```

## 1b-bis. The contract templates

The client's `.docx` contracts are their commercial and legal property and are
not shipped with the module. Put them on the server, import them, and delete
them — the same discipline as the values workbook:

```bash
uv run python manage.py import_contract_templates --dir /tmp/ka_contracts --inspect   # look first
uv run python manage.py import_contract_templates --dir /tmp/ka_contracts
rm -rf /tmp/ka_contracts
```

`--inspect` prints every blank it can see without writing anything. The real
run reports, per file, which clause groups it could NOT find — that is either a
contract which genuinely has no such clause (an initiative contract has no car
clause) or the client rewording a clause under us, and those look identical
from here, so a human reads the line.

Two files import as `*_reference`: they are copies of signed contracts with
their dates already typed in, not blank templates, and they are kept because
"why does this clause differ?" gets asked eventually.

**The client's values workbook** is loaded separately, because it is their
commercial data and is not shipped with the module:

```bash
# put the CSV on the server, load it, then delete it
uv run python manage.py load_official_values --file /tmp/official_values.csv --dry-run
uv run python manage.py load_official_values --file /tmp/official_values.csv
```

It REJECTS rows that fail a sanity check rather than guessing — a full tier
priced below its medium tier, or a reversed price range. Both are errors that
actually got through an earlier extraction of this same file. On `khaled_test`
it loaded 304 deposit values, 5 customs values and 63 price ranges with no
rejections.

## 1c. The two integrations, and their simulators

Both are written against the documented API and both ship with a simulator, so
the work did not wait on credentials that have not arrived:

```bash
uv run python manage.py search_mobile_de --status          # which backend would answer
uv run python manage.py search_mobile_de --make Mercedes-Benz --model C200 --import
uv run python manage.py sync_dropbox_calls --status
uv run python manage.py sync_dropbox_calls
```

Every run prints **which backend answered**, and every simulated row is stamped
`is_simulated` — a fake car must never drift into a customer's quote.

To go live, set config parameters and change no code:

| Integration | Config parameters |
|---|---|
| mobile.de | `car_import.mobile_de_username`, `car_import.mobile_de_password` |
| Dropbox | `car_import.dropbox_app_key`, `_app_secret`, `_refresh_token`, `_folder` |

## 1d. The organisation, and the deals already in flight

```bash
uv run python manage.py setup_car_import_org --report
uv run python manage.py setup_car_import_org --assign person@example.com=sales_agent
uv run python manage.py setup_car_import_org --branches

uv run python manage.py import_open_deals --file deals.csv --dry-run
uv run python manage.py import_open_deals --file deals.csv
```

Every imported deal is created with **customer messages held**, unconditionally.
`--release-messages` exists only to refuse: importing loudly is not something
anyone should be able to do by passing a flag. Lift the hold per deal, by hand,
once each customer knows a system is doing this — the next real stage move is
then their first automatic message.

## 2. Seed the stages

```bash
uv run python manage.py seed_import_stages
```

Creates the client's 14 stages (13 plus licensing as the final one) with the Arabic
drafts and **customer messages switched off**, and the `car_import.cardeal` sequence
that gives each deal its `KA/<year>/0001` reference. Do not skip it: without that
sequence row `SequenceMixin` gives up silently and every deal saves nameless.

Leave the messages off until Mr Khaled or the General Manager approves the wording and
WhatsApp approves the templates. Then:

```bash
uv run python manage.py seed_import_stages --enable-messages
```

## 3. Load the AI workflow

**Preferred — build it from code on the server.** This is what was used on
`khaled_test`; it resolves the model and the six tools against what the instance
actually has and prints which model it picked:

```bash
uv run python manage.py build_ka_workflows --voice aya
```

**Or** import a bundle through the UI — AI Studio → Workflows → Import → choose
`workflows/ka_sales.bundle.json`. The agent node carries two system messages: a cached static one (rules, voice, lane) and an uncached `<dynamic_context>` (customer, lead, deal, summary, last messages, warnings, per-account instructions). Tools and models
are carried by name, so pick the model in the node afterwards if the name differs.

Either way, verify the graph before anyone connects a number — one entry node, both
conditional handles wired, six tools resolving, no `ask_human` and no `human_approval`
(in a channel flow those park the run forever and the customer gets nothing), and the
workflow attached to **no** WhatsApp account yet:

```bash
uv run python manage.py shell -c "
from modules.aistudio.models import WorkflowDefinition, ToolDefinition
from modules.whatsapp.models import WhatsAppAccount
w = WorkflowDefinition.objects.get(name='KA Sales')
nodes = {n.node_id: n for n in w.nodes.all()}; edges = list(w.edges.all())
print('entry:', [n for n in nodes if n not in {e.target_node_id for e in edges}])
print('accounts:', list(WhatsAppAccount.objects.values_list('name', 'handled_by_ai', 'workflow_id')))"
```

Then open the agent node and confirm:

- the **model** and the **backup model** resolved (without a backup, a provider outage
  becomes the agent's reply text);
- all six tools are attached — if any is missing, run `sync_tools --app car_import` and
  rebuild;
- `error_message` is the Arabic hand-off sentence (the build command sets it; the bundle
  import does not carry it).

### Before a number: the evals

```bash
uv run python manage.py seed_ka_evals              # 9 golden cases
uv run python manage.py export_ka_workflow --voice aya   # a bundle for another instance
```

Every case is either a defect that reached this tenant or a rule the client
stated. Run them from AI Studio → Evals, and read the result honestly: runs are
**not sandboxed** so a side-effecting tool really fires, `max_cost` and
`max_steps` assertions can never fail, and `must_call_tools` is a substring
match. A pass means "nothing obvious broke", not proof.

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

The single most dangerous hour of the go-live: every deal in flight has to arrive at
the stage it is really at, and writing a stage fires the save hook that messages the
customer. So the import holds every message, and lifting the hold is a per-deal human
act, in this order:

```bash
# 1. the client's sheet, one row per open deal — columns in import_open_deals.py
uv run python manage.py import_open_deals --file deals.csv --dry-run   # read the problems
uv run python manage.py import_open_deals --file deals.csv             # creates them SUPPRESSED
# 2. an agent opens each deal, checks the stage and the customer, and — once the
#    customer has been told a system now sends these — unticks "Hold customer messages"
# 3. the next real stage move is that customer's first automatic message
```

There is no command that lifts the hold in bulk, on purpose. `import_open_deals
--release-messages` refuses.

## 6. The last mile: backups, contacts, demo data, people

```bash
# backups — on the host, nightly at 03:30 host time, fourteen days, never copied off
install -m 755 <(tr -d '\r' < ops/backup/genie-backup.sh) /usr/local/bin/genie-backup
install -m 644 ops/backup/genie-backup@.service ops/backup/genie-backup@.timer /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now genie-backup@<slug>.timer
systemctl start genie-backup@<slug>.service && ls -lh /var/backups/genie/<slug>/

# the company's contact list, deduplicated on the canonical phone
uv run python manage.py import_contacts --file contacts.csv --dry-run
uv run python manage.py import_contacts --file contacts.csv

# the people, into their groups (no passwords — they use the reset link)
uv run python manage.py setup_car_import_org --csv people.csv --dry-run
uv run python manage.py setup_car_import_org --csv people.csv
uv run python manage.py setup_car_import_org --report

# the demo rows, LAST, once the real data is in and before the first agent logs in
uv run python manage.py purge_demo_data                    # what would go
uv run python manage.py purge_demo_data --deal KA/2026/0002 --confirm
```

`purge_demo_data` refuses on a database whose name lacks `test` unless
`--i-mean-production` is passed. Restore notes are in `ops/backup/README.md`.

## What this release does

- The deal (`CarDeal`), the 13 stages, the change log and the car record.
- Every stage move logs and messages the customer — inside WhatsApp's 24-hour window as
  text, outside it as an approved template, on any other channel through the universal
  sender. A failure raises an activity for the agent instead of disappearing.
- Deal pipeline, form, list and search; car, stage and message-log screens.
- Identity fields on the contact, qualification on the lead, **Create car deal** on the lead.
- Six security groups and the install guard.
- An AI agent for WhatsApp/Messenger/Instagram/TikTok/web chat with eleven tools:
  deal status, send status, eligibility, instalment terms, fees, document
  checklist, vehicle and initiative search, initiative registration, follow-up
  scheduling, and hand-off to a human.
- **The price calculator**, ported cell for cell from the client's
  `New Quotation.xlsx`: five bands and seven fees as editable dated rows, an
  engine that refuses rather than guesses for a price no band covers, and
  `price_car --check` to prove it still matches their sheet.
- **Quotations** (`Quote`, `QuoteLine`): every figure frozen at the moment it
  was calculated, a payment box that takes a real amount instead of a status,
  an Arabic page to print, and a WhatsApp message to send — behind a
  confirmation, a kill switch and an opt-out check.
- **Contracts** (`Contract`, `ContractTemplate`): the client's own bilingual
  `.docx` files, blanks turned into named fields, filled from the deal and its
  accepted quotation and handed back as the same Word document. It refuses to
  produce a file when a required field did not land, because a contract with
  dots where the price belongs is a document somebody signs.
- **Review pages for the client**: `export_stage_messages` and
  `export_whatsapp_templates` write a link the client can read on a phone and
  forward, which is how the stage wording and the WhatsApp templates get
  approved without pasting fourteen messages into a chat thread.

## What it deliberately does not do yet

| Not built | Why / what unblocks it |
|---|---|
| mobile.de search | The account questions came back blank; Mr Khaled holds the account |
| Documents / KYC lane (vision) | Second AI lane; comes after the document checklist |
| Website tracking-page feed | Waiting on an introduction to their engineer, Ahmed Saeed |
| Call summaries from Dropbox | Separate module, `car_call_summary` |
| Out-of-hours AI after 30 minutes of agent silence | Lives in the inbound path, not in this graph |

## If it goes wrong

Roll back in this order: revert the commit (and **push**, or the next deploy restores the
bad version) → `sync_all`, which removes the view, menu and action rows → `migrate
car_import zero` only if the tables must go too → restart worker, gunicorn, daphne.

`sync_schema` never drops columns, so the fields added to contacts, leads and tickets stay
behind as nullable columns. That is harmless, and safer than dropping data.

To stop the AI without any deploy: `build_ka_workflows --rollback`. To stop stage messages
without any deploy: set the `car_import.stage_messages_enabled` config parameter to `0`,
or tick "Hold customer messages" on the deals concerned.

## Two behaviours worth knowing before you demo

- **Dragging a card in the kanban that a gate blocks reverts silently.** The board discards
  the server's message (a core renderer limitation), so the card just snaps back. The same
  move from the form or the status pill shows the real reason.
- **Every stage move messages the customer** — from a button, a kanban drag, an automation
  rule or a list bulk-edit alike, because the hook sits on the model's save. That is
  deliberate, and it is why the suppression switch exists for migration day.

## What the first install taught us

Every one of these was found by using the module on `khaled_test`, not by reading it.
They are fixed in the code; they are listed because each one would have looked like a
different problem from the screen.

| What you saw | What it actually was |
|---|---|
| "No form view found for this menu item" when opening any deal | The status header builds its pill options by reading `record.name` off the stage model (`ui_view.py:1146`). The stage called it `name_ar`, the AttributeError was swallowed into a 404. Migration 0002 renames it |
| A deal saved with an empty reference, chatter announcing "Car Deal '—'" | No `Sequence` row for `car_import.cardeal`. `SequenceMixin` skips numbering without one and says nothing (`mixins.py:249`). `seed_import_stages` now creates it |
| "Move to next stage" and "Send update to customer" did nothing, wherever you clicked | They were not there. The header lays the status pills and the buttons on one 30px row with overflow hidden, and fourteen Arabic stage names pushed both buttons to `x=-26, visibility:hidden`. The form no longer draws a status ribbon |
| The kanban was a flat wall of cards | A kanban only draws columns when the view names a `group_by` field. It now names `import_stage` |
| The lead had no car-import fields and no button | The eleven `ka_*` fields and the `@action` were on the model from day one, and no view ever showed them. `ui/views/lead_views.py` patches `crm_lead_form_view` |
| Instalments saved happily for a customer holding the initiative | The rule lived in `clean()`, and neither Django's `save()` nor this platform's write path calls it. It runs in `pre_save` now, where it becomes an HTTP 400 |
| `build_ka_workflows` refused: "No active LLM model named 'claude-sonnet-5'" | Two things: the tenant's model catalogue predates Claude 5, and the provider filter was `'Anthropic'` while providers are seeded lower-case. The definition now carries an ordered candidate list and the match is case-insensitive |

And from driving a whole Egyptian-Arabic conversation through the graph:

| What you saw | What it actually was |
|---|---|
| Every turn ended at the logger node; the agent never ran once | The gate compared `{{ prepare_turn.needs_ai }}` with `'true'` using `equals`. For `data_type: boolean` this engine implements **only** `is_true` / `is_false` / `is_empty` / `is_not_empty` (`workflow_engine.py:1445`); anything else logs "Unknown operator" and returns False. Every structural check passed, because the wiring was never wrong |
| The model was told "no open deal" about a customer whose car was at sea | A `function` node receives `partner` and `conversation` as **injected globals**, not inside `input_data` (`node_executor.py:_create_execution_context`) |
| `حالة الدفع حسب المسجّل عندنا: Not paid` — English inside the Arabic message | Customer text was built from the model's choice labels, which are gettext strings resolved against the active language; a tool runs in Celery with no request, so the active language is English |
| `Agent execution error: Anthropic authentication failed…` as the agent's answer | No provider on the tenant had an API key. Note the bridge treats an error in the output as a failure and escalates, so a customer would not see this — but they would get nothing from the AI either |

Two things that were **not** faults, so nobody re-investigates them: a burst of
`WebSocket error` lines in the browser console is the sockets dropping across a service
restart, and `sync_schema --status` reporting one pending `contenttypes.contenttype.name`
change belongs to `modules.base` and predates this module.

## Rules encoded here, so nobody has to remember them

- Instalments are refused when the customer holds the initiative himself.
- Any 3 of the 6 options put a car in the full deposit tier.
- The AI never states a down-payment percentage, never sends an account number, never
  confirms a transfer, and never computes an instalment amount.
- Cancellation never messages the customer automatically.
- The licence cost is never quoted; the licensing service fee is 3,000 EGP.
