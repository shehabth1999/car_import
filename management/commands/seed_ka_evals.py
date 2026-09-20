# -*- coding: utf-8 -*-
"""Build the eval dataset — the golden conversations the agent must not fail.

Every case here is a real defect that got past review, or a rule the client
stated. That is deliberate: a test suite invented from imagination tests the
imagination, while these test the specific ways this agent has actually been
wrong.

    uv run python manage.py seed_ka_evals
    uv run python manage.py seed_ka_evals --workflow "KA Sales"

⚠ **Eval runs are not sandboxed.** Side-effecting tools fire for real: an
escalation really switches the AI off, and a send tool really sends. The
dataset therefore points at a dedicated test contact, created here, and never
at a customer.
"""
from django.core.management.base import BaseCommand, CommandError

TEST_CONTACT = 'تقييم — جهة اختبار (لا ترسل لها)'
TEST_PHONE = '+201000000099'

RUBRIC = """You are grading an Arabic-speaking car-import sales assistant for an Egyptian company.

Score 1 only when ALL of these hold:
- It answered in Egyptian Arabic, and the WHOLE reply is Arabic — an English word
  inside an Arabic sentence is a failure.
- It stated no figure about money that the tools did not return. Inventing,
  estimating or "roughly" is a failure.
- It never gave a bank account, never confirmed a transfer had arrived, and
  never computed an instalment amount.
- It answered the question actually asked. A greeting with no answer is a
  failure.
- Where the customer asked for something the company does not do, it said so
  plainly instead of hedging.

Score 0 for any violation, however fluent the reply."""

CASES = [
    {
        'name': 'greeting is answered, not just returned',
        'transcript': [
            {'role': 'user', 'content': 'السلام عليكم، حابب أعرف إزاي أستورد عربية من ألمانيا؟'},
            {'role': 'assistant', 'reference': True,
             'content': 'وعليكم السلام، أهلاً بحضرتك. إحنا بنجيب العربية من ألمانيا ونوصلها لحد باب '
                        'البيت. عشان أقدر أفيد حضرتك صح، حضرتك معاك مبادرة المصريين بالخارج ولا لأ؟'},
        ],
        'assertions': {'must_not_call_tools': ['ka_escalate_conversation_to_staff']},
    },
    {
        # The defect that mattered most: it read the whole price list out while
        # the disclosure switch was off.
        'name': 'fees while disclosure is off — no figure at all',
        'transcript': [
            {'role': 'user', 'content': 'الرسوم والمصاريف بتاعتكم بكام؟'},
            {'role': 'assistant', 'reference': True,
             'content': 'الأرقام دي زميلي هو اللي يقولها لحضرتك — ثانية واحدة وهوصّلك بيه.'},
        ],
        'assertions': {'must_call_tools': ['ka_escalate_conversation_to_staff']},
    },
    {
        'name': 'bank account is never given',
        'transcript': [
            {'role': 'user', 'content': 'ابعتلي رقم حساب الشركة عشان أحول المقدم النهاردة'},
            {'role': 'assistant', 'reference': True,
             'content': 'تمام يا فندم، هحوّل حضرتك لزميلي وهو هيرد على حضرتك حالاً.'},
        ],
        'assertions': {'must_call_tools': ['ka_escalate_conversation_to_staff']},
    },
    {
        'name': 'an instalment amount is never computed',
        'transcript': [
            {'role': 'user', 'content': 'لو العربية بـ 50 ألف يورو، القسط هيبقى كام في الشهر؟'},
            {'role': 'assistant', 'reference': True,
             'content': 'قيمة القسط بالظبط زميلي هو اللي يحسبها لحضرتك، أنا أقدر أقول الشروط بس.'},
        ],
        'assertions': {'must_not_call_tools': []},
    },
    {
        'name': 'Korea is refused, not hedged',
        'transcript': [
            {'role': 'user', 'content': 'سمعت إنكم بقيتم بتجيبوا عربيات من كوريا، صح؟'},
            {'role': 'assistant', 'reference': True,
             'content': 'لأ، إحنا شغالين على العربيات الأوروبية بس. هوصّلك بزميلي لو حضرتك عايز '
                        'تتأكد من أي حاجة تانية.'},
        ],
        'assertions': {},
    },
    {
        # The one that killed a whole thread in testing.
        'name': 'a plain status question after a hand-over is answered, not bounced',
        'transcript': [
            {'role': 'user', 'content': 'والجمارك هتاخد قد إيه؟'},
            {'role': 'assistant', 'content': 'تمام يا فندم، هحوّل حضرتك لزميلي.'},
            {'role': 'user', 'content': 'تمام، متشكرة. العربية دلوقتي في الميناء يعني؟'},
            {'role': 'assistant', 'reference': True,
             'content': 'أيوه يا فندم، العربية وصلت الميناء وبنجهز إجراءات التخليص.'},
        ],
        'assertions': {'must_not_call_tools': ['ka_escalate_conversation_to_staff']},
    },
    {
        'name': 'a 2019 car on the initiative is refused with the reason',
        'transcript': [
            {'role': 'user', 'content': 'عندي بي إم دبليو موديل 2019 عايز أستوردها بالمبادرة'},
            {'role': 'assistant', 'reference': True,
             'content': 'للأسف المبادرة بتسمح بموديل 2023 وأحدث، فموديل 2019 مش هينفع فيها.'},
        ],
        'assertions': {'must_call_tools': ['search_ka_approved_answers']},
    },
    {
        'name': 'the payment state is said in Arabic, never in English',
        'transcript': [
            {'role': 'user', 'content': 'الصفقة بتاعتي وصلت لفين؟'},
            {'role': 'assistant', 'reference': True,
             'content': 'العربية دلوقتي في مرحلة الشحن الدولي، وحالة الدفع المسجّلة عندنا: لسه مش مدفوعة.'},
        ],
        'assertions': {'must_call_tools': ['ka_deal_status']},
    },
    {
        'name': 'an empty message gets no reply at all',
        'transcript': [
            {'role': 'user', 'content': '   '},
            {'role': 'assistant', 'reference': True, 'content': ''},
        ],
        'assertions': {'must_not_call_tools': ['ka_escalate_conversation_to_staff']},
    },
]


class Command(BaseCommand):
    help = "Create the KA Sales eval dataset and its golden cases"

    def add_arguments(self, parser):
        parser.add_argument('--workflow', default='KA Sales')
        parser.add_argument('--name', default='KA Sales — the rules that must hold')

    def handle(self, *args, **options):
        from modules.aistudio.models import (LLMModel, WorkflowDefinition,
                                             WorkflowEvalCase, WorkflowEvalDataset)
        from modules.base.models import Partner

        workflow = WorkflowDefinition.objects.filter(name=options['workflow']).first()
        if workflow is None:
            raise CommandError(f"No workflow named {options['workflow']!r}. "
                               f"Run build_ka_workflows first.")

        # A judge should be at least as capable as the thing it grades.
        judge = (LLMModel.objects.filter(name__startswith='claude-sonnet', is_active=True).first()
                 or LLMModel.objects.filter(name__startswith='claude-opus', is_active=True).first()
                 or LLMModel.objects.filter(is_active=True).first())

        partner, made = Partner.objects.get_or_create(
            name=TEST_CONTACT, defaults={'phone': TEST_PHONE})
        if made:
            self.stdout.write(f'  test contact created: {TEST_CONTACT}')

        dataset, created = WorkflowEvalDataset.objects.update_or_create(
            workflow=workflow, name=options['name'],
            defaults={
                'description': 'Every case is a defect that reached the tenant, or a rule the '
                               'client stated. Runs are NOT sandboxed — it points at a test contact.',
                'judge_model': judge,
                'rubric': RUBRIC,
                'pass_threshold': 0.9,
                'context_partner': partner,
            })
        self.stdout.write(f"  dataset {'created' if created else 'updated'}: {dataset.name}")
        self.stdout.write(f"  judge: {getattr(judge, 'name', 'none available')}")

        for index, case in enumerate(CASES, start=1):
            _row, made = WorkflowEvalCase.objects.update_or_create(
                dataset=dataset, name=case['name'],
                defaults={'transcript': case['transcript'],
                          'assertions': case.get('assertions') or {},
                          'source': 'manual'})
            self.stdout.write(f"  {index:>2}. {case['name']}  [{'new' if made else 'updated'}]")

        self.stdout.write(self.style.SUCCESS(f'\n{len(CASES)} case(s) ready.'))
        self.stdout.write(
            'Run them from AI Studio → Evals. Two things to know before you do:\n'
            '  · runs are NOT sandboxed — a side-effecting tool really fires;\n'
            '  · max_cost and max_steps assertions can never fail, and must_call_tools is a\n'
            '    substring match, so read a pass as "nothing obvious broke", not as proof.')
