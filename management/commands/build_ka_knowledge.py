# -*- coding: utf-8 -*-
"""Index the approved company answers so the assistant quotes them, not itself.

The knowledge base the client signed off exists as markdown in KHALED_DATA and
the assistant has answered from its prompt instead. This ships the customer-safe
part of that text inside the module (`knowledge/*.md`) and indexes it as one AI
Studio collection the agent node searches.

Two things were decided on purpose:

* **Every figure was stripped from the sources.** Prices, deposits, fees,
  percentages — none of it is in `knowledge/`. Money stays with the tools and
  the disclosure switch; a collection carrying prices is a second, uncontrolled
  price list that nobody dates and everybody quotes.
* **No `manage.py` indexing command exists in the platform** — indexing runs
  through the DRF view (`aistudio/api/rag_views.py:_process_document`). This
  does the same steps in the same order: load, split, store chunks, reindex.

Embeddings are OpenAI's; the key is the `openai` provider record, which the
tenant already has for its backup model. Re-running replaces the documents.

    uv run python manage.py build_ka_knowledge
    uv run python manage.py build_ka_knowledge --dry-run
"""
import os

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

#: What the collection is called. `build_ka_workflows` resolves it by this name.
# ASCII on purpose: the retriever's TOOL NAME is derived from this
# (`search_<name>`, node_executor.py:1687) and the providers accept only
# [a-zA-Z0-9_-]. An Arabic name here made every agent turn a 400.
COLLECTION_NAME = 'ka_approved_answers'
COLLECTION_TITLE = 'KA — الإجابات المعتمدة'
KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'knowledge')


class Command(BaseCommand):
    help = "Index knowledge/*.md as the assistant's approved-answers collection"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from modules.aistudio.api.rag_views import resolve_provider_key
        from modules.aistudio.models import Collection, DocumentChunk, RAGDocument
        from modules.aistudio.services.document_loader import DocumentLoaderService
        from modules.aistudio.services.rag_service import RAGService

        sources = sorted(f for f in os.listdir(KNOWLEDGE_DIR) if f.endswith('.md'))
        if not sources:
            raise CommandError(f'No .md files in {KNOWLEDGE_DIR}')
        self.stdout.write(f'{len(sources)} source(s): {", ".join(sources)}')

        # The figures are GENERATED from the settings tables, never hand-written
        # (services/knowledge_figures.py) — so they are exempt from the guard
        # below, which exists to keep a person from typing a price into prose.
        from car_import.services import knowledge_figures
        generated = knowledge_figures.documents()
        self.stdout.write(f'{len(generated)} generated: {", ".join(sorted(generated)) or "-"}'
                          + ('' if knowledge_figures.may_publish()
                             else '  (published figures are switched off)'))

        # Guard the one rule that matters: no money in the knowledge base.
        leaks = _money_leaks(sources)
        if leaks:
            for name, line in leaks:
                self.stdout.write(self.style.ERROR(f'  {name}: {line[:90]}'))
            raise CommandError('These lines look like figures. The knowledge base carries none.')

        if options['dry_run']:
            self.stdout.write('Dry run — nothing indexed.')
            return

        key = resolve_provider_key('openai')
        if not key:
            raise CommandError('No OpenAI key on the openai LLMProvider record; embeddings need one.')

        rag_config = settings.RAG_CONFIG
        loader = DocumentLoaderService(
            default_chunk_size=rag_config.get('DEFAULT_CHUNK_SIZE', 1000),
            default_chunk_overlap=rag_config.get('DEFAULT_CHUNK_OVERLAP', 200),
            max_file_size=rag_config.get('MAX_FILE_SIZE', 10485760),
            allowed_extensions=rag_config.get('ALLOWED_EXTENSIONS', []))
        service = RAGService(db_url=rag_config['DB_URL'], openai_api_key=key)

        with transaction.atomic():
            collection, created = Collection.objects.get_or_create(
                name=COLLECTION_NAME,
                defaults={'source_type': 'document', 'is_public': True,
                          'description': COLLECTION_TITLE + ' — الإجابات والسياسات المعتمدة، والأرقام المعلنة من جداول الإعدادات. '
                                         'Built by build_ka_knowledge from car_import/knowledge/.'})
            if created or not collection.is_indexed:
                result = service.create_collection(collection)
                if not result.get('success'):
                    raise CommandError(f'create_collection failed: {result.get("error")}')

            # Replace, never append: the markdown is the source of truth and a
            # re-run must leave exactly one copy of each file.
            RAGDocument.objects.filter(collection=collection, source_type='file',
                                       title__startswith='ka:').delete()

            items = []
            for name in sources:
                with open(os.path.join(KNOWLEDGE_DIR, name), 'rb') as handle:
                    items.append((name, handle.read()))
            items += [(name, text.encode('utf-8')) for name, text in sorted(generated.items())]

            total_chunks = 0
            for name, raw in items:
                # Stored as .txt, deliberately. The platform routes .md through
                # UnstructuredMarkdownLoader, which needs the `unstructured`
                # package the tenants do not carry; .txt goes through TextLoader
                # with no extra dependency, and markdown is plain text to an
                # embedding anyway. The source files in the module stay .md.
                stored = name[:-3] + '.txt'
                document = RAGDocument(collection=collection, source_type='file',
                                       title=f'ka:{name}', original_filename=stored,
                                       file_size=len(raw), file_type='txt', status='processing')
                document.file.save(stored, ContentFile(raw), save=False)
                document.save()

                loaded = loader.process_file(
                    file_path=document.file.path,
                    chunk_size=collection.chunk_size,
                    chunk_overlap=collection.chunk_overlap,
                    document_metadata={'document_id': str(document.id),
                                       'collection_id': str(collection.id),
                                       'filename': name})
                if not loaded.get('success'):
                    raise CommandError(f'{name}: {loaded.get("error")}')
                chunks = loaded['chunks']
                DocumentChunk.objects.bulk_create([
                    DocumentChunk(document=document, content=c.page_content, chunk_index=i,
                                  metadata=c.metadata, token_count=len(c.page_content) // 4)
                    for i, c in enumerate(chunks)])
                document.total_chunks = len(chunks)
                document.total_tokens = loaded.get('total_tokens', 0)
                document.status = 'completed'
                document.processed_at = timezone.now()
                document.save()
                total_chunks += len(chunks)
                self.stdout.write(f'  {name}: {len(chunks)} chunk(s)')

        result = service.reindex_collection(collection)
        if not result.get('success'):
            raise CommandError(f'reindex failed: {result.get("error")}')
        collection.refresh_from_db()
        self.stdout.write(self.style.SUCCESS(
            f'"{collection.name}" (id {collection.pk}) — {len(sources) + len(generated)} document(s), '
            f'{total_chunks} chunk(s), indexed={collection.is_indexed}'))
        self.stdout.write('Run `build_ka_workflows` so the agent node picks the collection up.')


def _money_leaks(sources):
    """Lines that read like a price. Durations and engine sizes are allowed."""
    import re
    money = re.compile(r'\d[\d.,]{2,}\s*(€|يورو|دولار|جنيه|ج\.م|EUR|USD|EGP|%|٪)')
    leaks = []
    for name in sources:
        with open(os.path.join(KNOWLEDGE_DIR, name), encoding='utf-8') as handle:
            for line in handle:
                if money.search(line):
                    leaks.append((name, line.strip()))
    return leaks
