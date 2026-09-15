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
LLM_MODEL_CANDIDATES = [
    ('claude-sonnet-5', 'Anthropic'),
    ('claude-opus-4-5-20251101', 'Anthropic'),
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

TOOL_NAMES = [
    'ka_get_deal_status',
    'ka_send_deal_status_update',
    'ka_check_import_eligibility',
    'ka_get_instalment_plan_terms',
    'ka_get_fee_and_licensing_costs',
    'ka_escalate_conversation_to_staff',
]

ERROR_MESSAGE = "بعتذر لحضرتك، هحوّل حضرتك لزميلي يكمل مع حضرتك دلوقتي."

# --------------------------------------------------------------------------- #
# prepare_turn — everything checkable, decided in Python before the model runs
# --------------------------------------------------------------------------- #
PREPARE_TURN_CODE = '''
def execute(input_data):
    """Facts and warnings for this turn. The model never looks anything up itself."""
    from django.utils import timezone

    partner = None
    ctx = input_data.get('context') or {}
    for source in (input_data, ctx):
        partner = partner or source.get('partner')
    partner_id = getattr(partner, 'pk', None) or ctx.get('partner_id') or input_data.get('partner_id')

    message = (input_data.get('partner_message') or input_data.get('message') or '')
    if isinstance(message, dict):
        message = message.get('text') or ''
    message = str(message)

    facts_lines, warnings, deal = [], [], None

    try:
        CarDeal = models['car_import']['CarDeal']
        if partner_id:
            deal = (CarDeal.all_objects
                    .select_related('vehicle', 'import_stage')
                    .filter(partner_id=partner_id)
                    .exclude(state='cancelled')
                    .order_by('-id')
                    .first())
    except Exception:
        deal = None

    if deal is not None:
        facts_lines.append('رقم الصفقة: %s' % (deal.name or '-'))
        if deal.vehicle_id:
            facts_lines.append('العربية: %s' % deal.vehicle)
        if deal.import_stage_id:
            facts_lines.append('المرحلة: %s' % (deal.import_stage.name or deal.import_stage.name_en))
        if deal.eta:
            facts_lines.append('الوصول المتوقع: %s' % deal.eta)
        if deal.arrival_port:
            facts_lines.append('الميناء: %s' % deal.arrival_port)
        facts_lines.append('حالة الدفع المسجّلة: %s' % deal.payment_state)
        if deal.payment_state != 'fully_paid':
            warnings.append('الصفقة مش معلّمة مدفوعة بالكامل: لو سأل عن الجمارك، التخليص مبيبدأش '
                            'قبل سداد المتبقي — وفي التقسيط القاعدة مختلفة، فحوّل لزميل.')
        if deal.program == 'initiative' and deal.customer_is_initiative_holder:
            warnings.append('العميل صاحب المبادرة: التقسيط مش متاح ليه.')

    text = message.lower()
    money_markers = ['رقم الحساب', 'رقم حساب', 'iban', 'لينك الدفع', 'لينك دفع', 'حولت', 'حوّلت',
                     'استرداد', 'ارجاع فلوس', 'خصم']
    if any(marker in text for marker in money_markers):
        warnings.append('الرسالة فيها طلب يخص الفلوس: استخدم أداة التحويل لزميل فوراً، '
                        'ومتبعتش أي بيانات بنكية ومتأكدش وصول أي تحويل.')

    if 'كوريا' in text or 'korea' in text:
        warnings.append('العميل ذكر كوريا: الشركة أوروبا بس، وفرع كوريا لسه غير مؤكد — حوّل لزميل.')

    if any(word in text for word in ['قسط', 'تقسيط', 'اقساط']):
        warnings.append('سؤال عن التقسيط: قول الشروط من الأداة، وعمرك ما تحسب قيمة قسط.')

    now = timezone.localtime()
    in_hours = now.weekday() <= 4 and 9 <= now.hour < 19

    return {
        'needs_ai': bool(message.strip()),
        'in_hours': in_hours,
        'deal_reference': (deal.name if deal is not None else ''),
        'deal_facts': ('\\n'.join(facts_lines) if facts_lines else 'مفيش صفقة مفتوحة للعميل ده.'),
        'warnings': ('\\n'.join('- ' + w for w in warnings) if warnings else 'مفيش تحذيرات.'),
    }
'''.strip()


def system_message_text(voice='aya'):
    """The agent's system prompt: the rules, the voice, and this turn's facts."""
    from car_import.agent_prompts import system_prompt

    return (
        system_prompt(voice)
        + "\n\n# بيانات الصفقة الحالية (من السيستم، مش من ذاكرتك)\n"
        + "{{ prepare_turn.deal_facts }}\n\n"
        + "# تحذيرات خاصة بالرسالة دي\n"
        + "{{ prepare_turn.warnings }}\n\n"
        + "# إرشادات الإدارة\n{{ instructions_text }}"
    )


def workflow_payload(voice='aya', system_text=None):
    """The workflow row's own fields."""
    titles = {'aya': 'Aya', 'ramy': 'Ramy', 'social': 'Social'}
    return {
        'name': f"KA Sales — {titles.get(voice, voice.title())}",
        'description': ("Customer conversations for Khaled Automobile / K&T. Python prepares the facts, "
                        "the agent reads meaning, and every money question goes to a human."),
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


def nodes(voice='aya', system_text=None):
    text = system_text if system_text is not None else system_message_text(voice)
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
                        'data_type': 'boolean',
                        'variable1': '{{ prepare_turn.needs_ai }}',
                        'operator': 'equals',
                        'variable2': 'true',
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
                'messages': [
                    {'role': 'system', 'cache': True, 'cache_ttl': '5m', 'text': text},
                ],
                'max_tokens': 4000,
                'enable_history': True,
                'memory_type': 'global',
                'response_type': 'user',
                'selected_tools': [
                    {'tool_id': None, 'ask_human': False, 'store': True} for _ in TOOL_NAMES
                ],
                'update_state': [{'key': 'current_lane', 'value_template': 'sales'}],
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
    ]
    for index, tool_name in enumerate(TOOL_NAMES):
        entries.append({
            'workflow_key': workflow_key, 'node_id': 'sales_agent', 'reference_kind': 'tool',
            'config_path': 'selected_tools', 'index': index, 'target_key': None,
            'target_name': tool_name,
        })
    return entries


def bundle(voice='aya', system_text=None, exported_at=None):
    """A complete AI Studio bundle, ready to import through the UI."""
    key = 'wf_1'
    payload = workflow_payload(voice)
    payload['nodes'] = nodes(voice, system_text=system_text)
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


def write_bundle(path, voice='aya', system_text=None, exported_at=None):
    data = bundle(voice=voice, system_text=system_text, exported_at=exported_at)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    return path
