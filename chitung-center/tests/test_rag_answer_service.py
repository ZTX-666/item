from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "chitung-center"))

from chitung_center.rag_service import RagService
from chitung_center.rag_service import _display_text, _filter_searchable_chunks, _is_mojibake_text
from chitung_center.models import ChatMessageRequest
from chitung_center.workflow_engine import WorkflowEngine


def test_rag_answer_calls_llm_with_retrieved_context_and_returns_citations():
    service = RagService()

    async def fake_query(query: str, top_k: int = 5, collection: str | None = None) -> dict[str, object]:
        assert query == "临边作业护栏要求是什么？"
        assert top_k == 3
        assert collection == "default"
        return {
            "ok": True,
            "query": query,
            "items": [
                {
                    "text": "临边作业防护栏杆应连续设置，并按项目制度进行闭环检查。",
                    "source_file_name": "site-safety.pdf",
                    "doc_id": "doc-1",
                    "chunk_index": 2,
                    "collection": "default",
                    "score": 0.12,
                }
            ],
        }

    async def fake_complete_json(system_prompt: str, user_text: str) -> dict[str, object]:
        assert "只根据给定知识库片段回答" in system_prompt
        assert "site-safety.pdf#chunk-2" in user_text
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"answer":"应连续设置防护栏杆，并保留闭环检查记录。",'
                            '"citations":[{"source_file_name":"site-safety.pdf","chunk_index":2}]}'
                        )
                    }
                }
            ]
        }

    with (
        patch.object(service, "query", new=AsyncMock(side_effect=fake_query)),
        patch("chitung_center.llm_gateway.llm_gateway.complete_json", new=AsyncMock(side_effect=fake_complete_json)),
    ):
        result = asyncio.run(
            service.answer_question("临边作业护栏要求是什么？", top_k=3, collection="default")
        )

    assert result["ok"] is True
    assert result["answer"] == "应连续设置防护栏杆，并保留闭环检查记录。"
    assert result["citations"] == [{"source_file_name": "site-safety.pdf", "chunk_index": 2}]
    assert result["matches"][0]["doc_id"] == "doc-1"


def test_rag_answer_returns_clear_empty_message_without_matches():
    service = RagService()

    with patch.object(
        service,
        "query",
        new=AsyncMock(return_value={"ok": True, "query": "无命中问题", "items": []}),
    ):
        result = asyncio.run(service.answer_question("无命中问题", top_k=5))

    assert result["ok"] is True
    assert "知识库里没有检索到" in result["answer"]
    assert result["citations"] == []
    assert result["matches"] == []


def test_rag_query_marks_garbled_pdf_chunks_as_low_quality():
    garbled = "+Efræ=ïà(æ)Ë)ä°IPEI^E åjô#tr¿ÈtË-- hÈE.# Ð;€!!tÈ f /rtE 29lt"
    assert _is_mojibake_text(garbled) is True
    assert _is_mojibake_text("处置地盘拆建物料的方法包括运往替代处置场地和物料堆放区。") is False


def test_rag_answer_does_not_send_garbled_chunks_to_llm():
    service = RagService()

    with (
        patch.object(
            service,
            "query",
            new=AsyncMock(
                return_value={
                    "ok": True,
                    "query": "处置地盘物料的方法有哪些",
                    "items": [
                        {
                            "text": "+Efræ=ïà(æ)Ë)ä°IPEI^E åjô#tr¿ÈtË-- hÈE.# Ð;€!!tÈ f /rtE 29lt",
                            "text_quality": "garbled",
                            "display_text": "该片段疑似 PDF 文字解析乱码。",
                            "source_file_name": "bad.pdf",
                            "doc_id": "doc-bad",
                            "chunk_index": 0,
                            "collection": "default",
                        }
                    ],
                }
            ),
        ),
        patch("chitung_center.llm_gateway.llm_gateway.complete_json", new=AsyncMock(side_effect=AssertionError("LLM should not receive garbled chunks"))),
    ):
        result = asyncio.run(service.answer_question("处置地盘物料的方法有哪些"))

    assert "解析质量较低" in result["answer"]
    assert result["citations"] == []


def test_rag_ingestion_filters_garbled_chunks_before_vectorizing():
    chunks = [
        "+Efræ=ïà(æ)Ë)ä°IPEI^E åjô#tr¿ÈtË-- hÈE.# Ð;€!!tÈ f /rtE 29lt",
        "處置地盤拆建物料時，應先分類、圍封堆放區，並按制度運往替代處置場地。",
    ]

    filtered = _filter_searchable_chunks(chunks)

    assert filtered == [chunks[1]]


def test_rag_display_text_trims_leading_pdf_extraction_noise():
    noisy = (
        ", -#4-1tu#i€ARfi{1\" :o wn $W' 1L€. HE{#K.. 5FFl.lffi.. "
        "fRE{ffi.. R4?#,€.. A|5&#,{.. ifrEi#K.. * "
        "拆卸側向承托(ELS)安全工作指引 一、目的 為加強對地盤拆卸工作的安全管理。"
    )

    display = _display_text(noisy, "normal")

    assert display.startswith("拆卸側向承托")
    assert "1tu#i" not in display


def test_rag_ask_api_exposes_llm_answer(monkeypatch):
    from fastapi.testclient import TestClient

    from chitung_center.app import app

    async def fake_answer_question(question: str, top_k: int = 5, collection: str | None = None) -> dict[str, object]:
        assert question == "吊装作业要检查什么？"
        assert top_k == 4
        assert collection == "default"
        return {
            "ok": True,
            "query": question,
            "answer": "重点检查吊装半径、指挥信号和隔离围挡。",
            "citations": [{"source_file_name": "lifting.md", "chunk_index": 1}],
            "matches": [],
        }

    monkeypatch.setattr("chitung_center.app.rag_service.answer_question", fake_answer_question)

    response = TestClient(app).post(
        "/api/rag/ask",
        json={"query": "吊装作业要检查什么？", "top_k": 4, "collection": "default"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "重点检查吊装半径、指挥信号和隔离围挡。"
    assert data["citations"] == [{"source_file_name": "lifting.md", "chunk_index": 1}]


def test_knowledge_workflow_uses_rag_answer_before_legacy_policy_search():
    async def fake_answer_question(question: str, top_k: int = 5, collection: str | None = None) -> dict[str, object]:
        assert question == "临边作业有哪些制度要求？"
        assert top_k == 5
        assert collection is None
        return {
            "ok": True,
            "query": question,
            "answer": "临边作业应设置连续防护栏杆，并完成整改闭环。",
            "citations": [{"source_file_name": "policy.md", "chunk_index": 4}],
            "matches": [
                {
                    "text": "临边作业应设置连续防护栏杆。",
                    "source_file_name": "policy.md",
                    "doc_id": "doc-1",
                    "chunk_index": 4,
                    "collection": "default",
                }
            ],
        }

    with (
        patch("chitung_center.workflow_engine.rag_service.answer_question", new=AsyncMock(side_effect=fake_answer_question)),
        patch("chitung_center.workflow_engine._safe_tool", new=AsyncMock(side_effect=AssertionError("legacy search should not run"))),
        patch("chitung_center.workflow_engine._start_step", new=AsyncMock(return_value={"workflow_step_id": "step-1"})),
        patch("chitung_center.workflow_engine._finish_step", new=AsyncMock()),
    ):
        reply, tool_results, cards = asyncio.run(
            WorkflowEngine()._run_knowledge_query(
                ChatMessageRequest(message="临边作业有哪些制度要求？"),
                "run-knowledge",
            )
        )

    assert reply == "临边作业应设置连续防护栏杆，并完成整改闭环。"
    assert tool_results[0]["tool"] == "rag_ask"
    assert cards[0].card_type == "rag_answer"
    assert cards[0].data["citations"] == [{"source_file_name": "policy.md", "chunk_index": 4}]
