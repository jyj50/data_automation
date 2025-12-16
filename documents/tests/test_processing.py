import io
from unittest import mock

import fitz
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from documents import services
from documents.models import ArticleChunk, Document, DocumentStatus, ProcessingStatus
from documents.services import (
    compute_checksum,
    generate_questions,
    ingest_document,
    parse_document_range,
    regex_structure_pages,
    search_similar_chunks,
    upsert_document,
)


def make_pdf_bytes(pages):
    """Utility to build a small PDF in-memory for tests."""
    buffer = io.BytesIO()
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    doc.save(buffer)
    doc.close()
    buffer.seek(0)
    return buffer.getvalue()


class RegexParsingTests(TestCase):
    def test_regex_extracts_articles(self):
        pages = [
            (1, "제1조(목적)\n내용\n제2조(정의)\n내용"),
        ]
        payload = regex_structure_pages(pages)
        self.assertEqual(len(payload.articles), 2)
        self.assertEqual(payload.articles[0].article_key, "제1조")
        self.assertEqual(payload.articles[1].article_key, "제2조")


class DocumentPipelineTests(TestCase):
    @override_settings(LLM_PROVIDER="none")
    def test_ingest_and_parse_range(self):
        pdf_bytes = make_pdf_bytes(["제1조(목적)\n내용", "제2조(정의)\n내용"])
        checksum = compute_checksum(io.BytesIO(pdf_bytes))
        upload = SimpleUploadedFile("sample.pdf", pdf_bytes, content_type="application/pdf")
        document = Document.objects.create(
            original_filename=upload.name,
            file=upload,
            checksum=checksum,
        )

        ingest_document(document)
        document.refresh_from_db()
        self.assertEqual(document.status, DocumentStatus.COMPLETED)
        self.assertEqual(document.pages.count(), 2)

        result = parse_document_range(document, 1, 2, mode="regex", force_reparse=True)
        document.refresh_from_db()
        self.assertEqual(document.parse_status, ProcessingStatus.COMPLETED)
        self.assertEqual(result["article_count"], 2)
        self.assertTrue(ArticleChunk.objects.filter(article__document=document).exists())

    @override_settings(LLM_PROVIDER="none", EMBEDDING_PROVIDER="none", VECTOR_DB_PROVIDER="none")
    def test_upsert_skips_when_disabled(self):
        pdf_bytes = make_pdf_bytes(["제1조(목적)\n내용"])
        checksum = compute_checksum(io.BytesIO(pdf_bytes))
        upload = SimpleUploadedFile("sample.pdf", pdf_bytes, content_type="application/pdf")
        document = Document.objects.create(
            original_filename=upload.name,
            file=upload,
            checksum=checksum,
        )
        ingest_document(document)
        parse_document_range(document, 1, 1, mode="regex", force_reparse=True)
        summary = upsert_document(document)
        self.assertTrue(summary.get("skipped"))
        self.assertEqual(document.upsert_status, ProcessingStatus.COMPLETED)

    @override_settings(LLM_PROVIDER="none")
    def test_question_generation_fallback(self):
        pdf_bytes = make_pdf_bytes(["제1조(목적)\n내용"])
        checksum = compute_checksum(io.BytesIO(pdf_bytes))
        upload = SimpleUploadedFile("sample.pdf", pdf_bytes, content_type="application/pdf")
        document = Document.objects.create(
            original_filename=upload.name,
            file=upload,
            checksum=checksum,
        )
        ingest_document(document)
        parse_document_range(document, 1, 1, mode="regex", force_reparse=True)
        result = generate_questions(document, per_article=2, scope="article")
        self.assertGreaterEqual(result.get("created", 0), 2)

    @override_settings(
        LLM_PROVIDER="none", EMBEDDING_PROVIDER="test", VECTOR_DB_PROVIDER="chroma", CHROMA_URL="http://chroma:8000"
    )
    def test_chroma_upsert_invokes_client(self):
        pdf_bytes = make_pdf_bytes(["제1조(목적)\n내용"])
        checksum = compute_checksum(io.BytesIO(pdf_bytes))
        upload = SimpleUploadedFile("sample.pdf", pdf_bytes, content_type="application/pdf")
        document = Document.objects.create(
            original_filename=upload.name,
            file=upload,
            checksum=checksum,
        )
        ingest_document(document)
        parse_document_range(document, 1, 1, mode="regex", force_reparse=True)

        class FakeCollection:
            def __init__(self):
                self.upserts = []

            def upsert(self, **kwargs):
                self.upserts.append(kwargs)

        class FakeEmbedder:
            def __init__(self):
                self.called = 0

            def encode(self, text):
                self.called += 1
                return [0.1, 0.2, 0.3]

        fake_collection = FakeCollection()
        fake_embedder = FakeEmbedder()

        services._get_embedder.cache_clear()
        services._get_chroma_collection.cache_clear()

        with mock.patch.object(services, "_get_chroma_collection", return_value=fake_collection), mock.patch.object(
            services, "_get_embedder", return_value=fake_embedder
        ):
            summary = upsert_document(document)

        self.assertFalse(summary.get("error"))
        self.assertEqual(document.upsert_status, ProcessingStatus.COMPLETED)
        self.assertTrue(fake_collection.upserts)
        self.assertGreater(fake_embedder.called, 0)

    @override_settings(
        LLM_PROVIDER="none", EMBEDDING_PROVIDER="test", VECTOR_DB_PROVIDER="chroma", CHROMA_URL="http://chroma:8000"
    )
    def test_chroma_search_returns_results(self):
        class FakeCollection:
            def __init__(self):
                self.queries = []

            def query(self, query_embeddings, n_results):
                self.queries.append((query_embeddings, n_results))
                return {
                    "ids": [["doc-1"]],
                    "metadatas": [
                        [
                            {
                                "chunk_index": 1,
                                "article_key": "제1조",
                                "chapter_title": "",
                                "section_title": "",
                                "source_pages": [1],
                                "document_id": 1,
                            }
                        ]
                    ],
                    "distances": [[0.12]],
                }

        class FakeEmbedder:
            def encode(self, text):
                return [0.5, 0.1, 0.9]

        services._get_embedder.cache_clear()
        services._get_chroma_collection.cache_clear()

        with mock.patch.object(services, "_get_chroma_collection", return_value=FakeCollection()), mock.patch.object(
            services, "_get_embedder", return_value=FakeEmbedder()
        ):
            results = search_similar_chunks("query", top_k=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["article_key"], "제1조")
