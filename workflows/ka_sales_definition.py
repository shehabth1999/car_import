# -*- coding: utf-8 -*-
"""
The KA Sales agent graph, as data.

One definition, two consumers: `build_ka_workflows` creates the rows directly on
a server, and `export_ka_workflow` writes an AI Studio bundle you can import
through the UI on a machine you cannot reach from here.

Design notes that are easy to get wrong (they come from this platform's
production rules, not from taste):

* `partner_flow` carries no approval surface. A `human_approval` node, an
  `ask_questions` block or a tool with `ask_human: true` would park the run
  forever and the customer would get nothing. None are used here.
* The entry node is the one with no incoming edge — `prepare_turn`.
* Every conditional branch must be wired: handle "1" for the first condition,
  "0" for else. An unwired handle crashes the run.
* Python decides whatever is checkable; the model only reads meaning.
"""
import json
import os

BUNDLE_FORMAT = 'aistudio.workflow.bundle'
BUNDLE_FORMAT_VERSION = 2

#: Resolved by name, best first, against whatever this instance actually has.
#: A single hard-coded name is how the build died on the first tenant it met:
#: its LLMModel table was seeded before Claude 5 existed, so the command
#: refused to build anything at all. The first name that resolves wins; the
#: build reports which one it used.
#: Haiku first, deliberately. This agent routes, reads intent and calls six
#: tools — it does not reason its way through anything hard, because Python
#: decided everything checkable before the model ever ran. Opus was costing
#: real money per customer turn for work Haiku does. Move Sonnet up if quality
#: measurably drops on the evals; do not move Opus up without a reason.
LLM_MODEL_CANDIDATES = [
    ('claude-haiku-4-5-20251001', 'Anthropic'),
    ('claude-sonnet-5', 'Anthropic'),
    ('claude-sonnet-4-5-20250929', 'Anthropic'),
]
BACKUP_LLM_MODEL_CANDIDATES = [
    ('gpt-5', 'OpenAI'),
    ('gpt-4.1-2025-04-14', 'OpenAI'),
    ('claude-haiku-4-5-20251001', 'Anthropic'),
]

#: What the exported bundle names. The importer resolves it by name and the
#: model can be repicked in the node afterwards.
LLM_MODEL_NAME = LLM_MODEL_CANDIDATES[0][0]
LLM_PROVIDER_NAME = LLM_MODEL_CANDIDATES[0][1]
BACKUP_LLM_MODEL_NAME = BACKUP_LLM_MODEL_CANDIDATES[0][0]
BACKUP_LLM_PROVIDER_NAME = BACKUP_LLM_MODEL_CANDIDATES[0][1]

#: What the agent can actually do. A tool that is registered but not listed
#: here is a tool the agent cannot reach — six were built and stranded that way
#: until a review caught it.
#:
#: `ka_log_call_outcome` is deliberately absent: it files what a PHONE call
#: decided, which is a human's job, and handing it to a chat agent invites it to
#: write minutes for a conversation that never happened.
TOOL_NAMES = [
    'ka_get_deal_status',
    'ka_send_deal_status_update',
    'ka_check_import_eligibility',
    'ka_get_instalment_plan_terms',
    'ka_get_fee_and_licensing_costs',
    'ka_get_document_checklist',
    'ka_search_vehicle_listings',
    'ka_search_initiative_listings',
    'ka_register_initiative_for_sale',
    'ka_schedule_followup',
    'ka_escalate_conversation_to_staff',
    'ka_share_bank_details',
    'ka_file_customer_document',
    # The sale itself — the client's decision of 2026-09-20 (services/policy.py).
    'ka_search_showroom_cars',
    'ka_send_car_photos',
    'ka_price_car',
    'ka_send_quotation',
    'ka_issue_proforma_invoice',
    'ka_record_payment_receipt',
    'ka_save_contract_details',
    'ka_request_discount',
]

#: The approved-answers collection `build_ka_knowledge` indexes. Resolved by
#: name at build time; the node carries the id. A tenant without it gets an
#: agent with no retriever rather than a broken one.
KNOWLEDGE_COLLECTION_NAME = 'ka_approved_answers'   # ASCII: it becomes the tool name

ERROR_MESSAGE = "بعتذر لحضرتك، هحوّل حضرتك لزميلي يكمل مع حضرتك دلوقتي."

# --------------------------------------------------------------------------- #
# prepare_turn — everything checkable, decided in Python before the model runs
# --------------------------------------------------------------------------- #
PREPARE_TURN_CODE = '''
def execute(input_data):
    """Facts and warnings for this turn. The model never looks anything up itself.

    Everything is built in the package (car_import/services/turn_context.py):
    this box caps near 10,000 characters, and a function in git is reviewable.
    `partner` and `conversation` are INJECTED GLOBALS in a function node's
    sandbox (node_executor.py:_create_execution_context), not input_data keys.
    """
    from django.utils import timezone
    from car_import.services import turn_context

    try:
        who = partner
    except NameError:
        who = None
    try:
        convo = conversation
    except NameError:
        convo = None

    message = (input_data.get('partner_message') or input_data.get('message') or '')
    if isinstance(message, dict):
        message = message.get('text') or ''
    message = str(message)

    now = timezone.localtime()
    result = turn_context.build(who, convo, message)
    result['needs_ai'] = bool(message.strip())
    result['in_hours'] = now.weekday() <= 4 and 9 <= now.hour < 19
    return result
'''.strip()


WORKFLOW_NAME = 'KA Sales'


def system_message_text():
    """The STATIC system message: the rules, the voice, the lane. Cached.

    Nothing in it changes between turns — that is what makes the Anthropic
    prompt cache hit. Everything that does change is in `dynamic_message_text`.
    """
    from car_import.agent_prompts import system_prompt

    return (
        system_prompt()
        + "\n\n# مصدر الحقائق\n"
        + "بيانات العميل والصفقة والمحادثة والتحذيرات وإرشادات الإدارة بتوصلك في الرسالة اللي بعد دي "
        + "(<dynamic_context>). هي المرجع، مش ذاكرتك."
    )


def dynamic_message_text():
    """The DYNAMIC system message, never cached: this turn's facts.

    The shape the other live agents use (maalem, basma): one `<dynamic_context>`
    block carrying who the customer is, where the conversation stands, the
    running summary, the last few messages, and the per-account instructions.
    Ours adds the deal facts and the per-message warnings `prepare_turn` built.
    """
    return (
        "<dynamic_context>\n"
        "دلوقتي: {{ now() }}\n"
        "القناة: {{ prepare_turn.channel_label }}\n"
        "إحنا: فريق مبيعات خالد أوتوموبيل / K&T\n"
        "\n"
        "# العميل (من السيستم، مش من ذاكرتك)\n"
        "{{ prepare_turn.partner_facts }}\n"
        "\n"
        "# الصفقة الحالية\n"
        "{{ prepare_turn.deal_facts }}\n"
        "\n"
        "# حالة البيع (عرض السعر / الفاتورة المبدئية / التحويلات / العقد)\n"
        "{{ prepare_turn.sales_facts }}\n"
        "\n"
        "{% if conversation and conversation.summary %}"
        "# ملخص المحادثة لحد دلوقتي\n"
        "{{ conversation.summary }}\n"
        "\n"
        "{% endif %}"
        "# آخر الرسايل (للتذكير — الرد على اللي جاي في رسالة العميل)\n"
        "{{ prepare_turn.recent_messages }}\n"
        "\n"
        "# تحذيرات خاصة بالرسالة دي\n"
        "{{ prepare_turn.warnings }}\n"
        "\n"
        "# إرشادات الإدارة\n"
        "{{ instructions_text }}\n"
        "{% if conversation and conversation.social_account and conversation.social_account.instructions %}"
        "\n# إرشادات خاصة بالرقم/الحساب ده\n"
        "{{ conversation.social_account.instructions }}\n"
        "{% endif %}"
        "{% if conversation and conversation.meta_ad_instructions %}"
        "\n# الإعلان اللي جاب العميل\n"
        "{{ conversation.meta_ad_instructions }}\n"
        "{% endif %}"
        "</dynamic_context>"
    )


def workflow_payload():
    """The workflow row's own fields. One workflow serves every number and channel."""
    return {
        'name': WORKFLOW_NAME,
        'description': ("Customer conversations for Khaled Automobile / K&T. Python prepares the facts, "
                        "the agent runs the sale — price, quotation, proforma invoice, transfer screenshot — "
                        "and a person only confirms that money arrived."),
        'category': 'sales',
        'version': 1,
        'workflow_type': 'partner_flow',
        'settings': {},
        'global_configuration': {
            'recursion_limit': 40,
            'state_injections': [
                {'key': 'current_lane', 'type': 'str', 'initial_value': 'sales', 'persist': True},
            ],
        },
        'timeout_seconds': 300,
        'max_retries': 1,
        'handles_comments': False,
        'is_public': False,
    }


def nodes(system_text=None):
    text = system_text if system_text is not None else system_message_text()
    dynamic = dynamic_message_text()
    return [
        {
            'node_id': 'prepare_turn',
            'node_type': 'function',
            'label': 'Prepare turn',
            'configuration': {
                'code': PREPARE_TURN_CODE,
                'description': 'Loads the customer\'s open deal, builds the facts block and this turn\'s warnings.',
            },
            'x_position': 0, 'y_position': 0,
            'width': 240, 'height': 100, 'color': '', 'enabled': True,
            'continue_on_error': False, 'timeout_seconds': 60, 'retry_count': 0,
        },
        {
            'node_id': 'gate_needs_ai',
            'node_type': 'conditional',
            'label': 'Needs the agent?',
            'configuration': {
                'conditions': [
                    {
                        # `boolean` implements ONLY is_true / is_false /
                        # is_empty / is_not_empty (workflow_engine.py:1445).
                        # 'equals' falls through to "Unknown operator" and
                        # returns False, so every turn took the else branch and
                        # the agent never ran once.
                        'data_type': 'boolean',
                        'variable1': '{{ prepare_turn.needs_ai }}',
                        'operator': 'is_true',
                        'variable2': '',
                    },
                ],
            },
            'x_position': 320, 'y_position': 0,
            'width': 220, 'height': 100, 'color': '', 'enabled': True,
            'continue_on_error': False, 'timeout_seconds': 30, 'retry_count': 0,
        },
        {
            'node_id': 'handled_in_python',
            'node_type': 'logger',
            'label': 'Handled without the model',
            'configuration': {
                'message': 'car_import: turn ended without the model (empty or system message).',
                'log_level': 'INFO',
            },
            'x_position': 640, 'y_position': 160,
            'width': 220, 'height': 90, 'color': '', 'enabled': True,
            'continue_on_error': True, 'timeout_seconds': 30, 'retry_count': 0,
        },
        {
            'node_id': 'sales_agent',
            'node_type': 'agent_chat',
            'label': 'Sales agent',
            'configuration': {
                'llm_model_id': None,
                'backup_llm_model_id': None,
                # Two system rows, on purpose: the first is stable and cached
                # (rules, voice, lane); the second is this turn's facts and is
                # never cached. One cached row holding both would miss the
                # cache on every turn and cost the full prompt each time.
                'messages': [
                    {'role': 'system', 'cache': True, 'cache_ttl': '5m', 'text': text},
                    {'role': 'system', 'cache': False, 'text': dynamic},
                ],
                'max_tokens': 4000,
                'enable_history': True,
                'memory_type': 'global',
                'response_type': 'user',
                'selected_tools': [
                    {'tool_id': None, 'ask_human': False, 'store': True} for _ in TOOL_NAMES
                ],
                'update_state': [{'key': 'current_lane', 'value_template': 'sales'}],
                # The approved answers, searched as a tool. `collection_id` is
                # filled by build_ka_workflows; the block is dropped when the
                # collection is not indexed on this tenant.
                'rag_retriever': {
                    'enabled': True,
                    'collections': [{'collection_id': None, 'search_type': 'mmr', 'k': 3,
                                     'tool_description': 'ابحث في الإجابات والسياسات المعتمدة من الشركة: '
                                                         'الإجراءات، المستندات، المدد، البرامج وشروطها. '
                                                         'مفيش أرقام فيها — الأرقام من الأدوات التانية.'}],
                },
            },
            'x_position': 640, 'y_position': -40,
            'width': 260, 'height': 120, 'color': '', 'enabled': True,
            'continue_on_error': False, 'timeout_seconds': 180, 'retry_count': 0,
        },
    ]


EDGES = [
    {'source_node_id': 'prepare_turn', 'target_node_id': 'gate_needs_ai', 'source_handle': '',
     'target_handle': '', 'condition': None, 'priority': 0, 'label': '', 'style': {}},
    {'source_node_id': 'gate_needs_ai', 'target_node_id': 'sales_agent', 'source_handle': '1',
     'target_handle': '', 'condition': None, 'priority': 0, 'label': 'needs the agent', 'style': {}},
    {'source_node_id': 'gate_needs_ai', 'target_node_id': 'handled_in_python', 'source_handle': '0',
     'target_handle': '', 'condition': None, 'priority': 0, 'label': 'nothing to answer', 'style': {}},
]


def reference_manifest(workflow_key='wf_1'):
    """Names the importer resolves to local ids on the target instance."""
    entries = [
        {'workflow_key': workflow_key, 'node_id': 'sales_agent', 'reference_kind': 'llm_model',
         'config_path': 'llm_model_id', 'index': None, 'target_key': None,
         'target_name': LLM_MODEL_NAME, 'target_provider': LLM_PROVIDER_NAME},
        {'workflow_key': workflow_key, 'node_id': 'sales_agent', 'reference_kind': 'llm_model',
         'config_path': 'backup_llm_model_id', 'index': None, 'target_key': None,
         'target_name': BACKUP_LLM_MODEL_NAME, 'target_provider': BACKUP_LLM_PROVIDER_NAME},
        {'workflow_key': workflow_key, 'node_id': 'sales_agent', 'reference_kind': 'collection',
         'config_path': 'rag_retriever.collections', 'index': 0, 'target_key': 'collection_id',
         'target_name': KNOWLEDGE_COLLECTION_NAME},
    ]
    for index, tool_name in enumerate(TOOL_NAMES):
        entries.append({
            'workflow_key': workflow_key, 'node_id': 'sales_agent', 'reference_kind': 'tool',
            'config_path': 'selected_tools', 'index': index, 'target_key': None,
            'target_name': tool_name,
        })
    return entries


def bundle(system_text=None, exported_at=None):
    """A complete AI Studio bundle, ready to import through the UI."""
    key = 'wf_1'
    payload = workflow_payload()
    payload['nodes'] = nodes(system_text=system_text)
    payload['edges'] = list(EDGES)
    return {
        'format': BUNDLE_FORMAT,
        'format_version': BUNDLE_FORMAT_VERSION,
        'root_key': key,
        'metadata': {
            'exported_at': exported_at or '',
            'exported_by': 'car_import/ka_sales_definition.py',
            'note': ("Import through AI Studio → Workflows → Import. Tools and models resolve by name; "
                     "check the agent node's model and backup model after importing."),
        },
        'workflows': {key: payload},
        'reference_manifest': reference_manifest(key),
    }


def write_bundle(path, system_text=None, exported_at=None):
    data = bundle(system_text=system_text, exported_at=exported_at)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    return path
