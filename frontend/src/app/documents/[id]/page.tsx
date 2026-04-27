"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, Document, DocumentPage, Article } from "@/lib/api";

type Tab = "pages" | "articles";

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const docId = Number(id);

  const [doc, setDoc] = useState<Document | null>(null);
  const [pages, setPages] = useState<DocumentPage[]>([]);
  const [tab, setTab] = useState<Tab>("pages");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Parse form state
  const [pageStart, setPageStart] = useState(1);
  const [pageEnd, setPageEnd] = useState(0);
  const [parseMode, setParseMode] = useState<"hybrid" | "regex" | "llm">("hybrid");
  const [parsing, setParsing] = useState(false);
  const [upserting, setUpserting] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const loadDoc = async () => {
    try {
      const [d, p] = await Promise.all([api.documents.get(docId), api.documents.pages(docId)]);
      setDoc(d);
      setPages(p.pages);
      setPageEnd(d.page_count);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDoc();
  }, [docId]);

  const handleParse = async () => {
    setParsing(true);
    setActionMsg(null);
    try {
      const res = await api.documents.parse(docId, {
        page_start: pageStart,
        page_end: pageEnd || doc?.page_count,
        mode: parseMode,
      });
      setActionMsg(`파싱 완료 — Article ${res.article_count}개`);
      await loadDoc();
    } catch (e) {
      setActionMsg(`파싱 오류: ${e}`);
    } finally {
      setParsing(false);
    }
  };

  const handleUpsert = async () => {
    setUpserting(true);
    setActionMsg(null);
    try {
      await api.documents.upsert(docId);
      setActionMsg("ChromaDB 업서트 완료");
      await loadDoc();
    } catch (e) {
      setActionMsg(`업서트 오류: ${e}`);
    } finally {
      setUpserting(false);
    }
  };

  if (loading) return <p style={{ padding: "2rem" }}>로딩 중…</p>;
  if (error) return <p style={{ padding: "2rem", color: "red" }}>{error}</p>;
  if (!doc) return null;

  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: "2rem" }}>
      <Link href="/">← 목록으로</Link>
      <h1 style={{ marginTop: "1rem" }}>{doc.original_filename}</h1>

      <dl style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: "4px 16px", marginBottom: "1.5rem" }}>
        <dt>상태</dt><dd>{doc.status}</dd>
        <dt>페이지 수</dt><dd>{doc.page_count}</dd>
        <dt>파싱 상태</dt><dd>{doc.parse_status}</dd>
        <dt>업서트 상태</dt><dd>{doc.upsert_status}</dd>
      </dl>

      {/* Actions */}
      <section style={{ background: "#f3f4f6", padding: "1rem", borderRadius: 8, marginBottom: "1.5rem" }}>
        <h2 style={{ margin: "0 0 0.75rem" }}>작업</h2>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <label>
            시작 페이지{" "}
            <input
              type="number" min={1} max={doc.page_count}
              value={pageStart}
              onChange={(e) => setPageStart(Number(e.target.value))}
              style={{ width: 60 }}
            />
          </label>
          <label>
            끝 페이지{" "}
            <input
              type="number" min={1} max={doc.page_count}
              value={pageEnd}
              onChange={(e) => setPageEnd(Number(e.target.value))}
              style={{ width: 60 }}
            />
          </label>
          <select value={parseMode} onChange={(e) => setParseMode(e.target.value as typeof parseMode)}>
            <option value="hybrid">Hybrid</option>
            <option value="regex">Regex only</option>
            <option value="llm">LLM only</option>
          </select>
          <button onClick={handleParse} disabled={parsing}>
            {parsing ? "파싱 중…" : "파싱 실행"}
          </button>
          <button onClick={handleUpsert} disabled={upserting}>
            {upserting ? "업서트 중…" : "ChromaDB 업서트"}
          </button>
        </div>
        {actionMsg && <p style={{ margin: "0.5rem 0 0", color: "#374151" }}>{actionMsg}</p>}
      </section>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, marginBottom: "1rem" }}>
        {(["pages", "articles"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: "6px 16px",
              background: tab === t ? "#2563eb" : "#e5e7eb",
              color: tab === t ? "#fff" : "#374151",
              border: "none",
              borderRadius: 6,
              cursor: "pointer",
            }}
          >
            {t === "pages" ? `페이지 (${pages.length})` : `Article (${doc.articles?.length ?? 0})`}
          </button>
        ))}
      </div>

      {tab === "pages" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12 }}>
          {pages.map((p) => (
            <div key={p.page_number} style={{ border: "1px solid #e5e7eb", borderRadius: 8, overflow: "hidden" }}>
              {p.preview_url ? (
                <img
                  src={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}${p.preview_url}`}
                  alt={`페이지 ${p.page_number}`}
                  style={{ width: "100%", display: "block" }}
                  loading="lazy"
                />
              ) : (
                <div style={{ height: 120, background: "#f3f4f6", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  미리보기 없음
                </div>
              )}
              <p style={{ margin: 0, padding: "4px 8px", fontSize: 12, color: "#6b7280" }}>
                p.{p.page_number} {p.has_text ? "" : "(텍스트 없음)"}
              </p>
            </div>
          ))}
        </div>
      )}

      {tab === "articles" && (
        <div>
          {(doc.articles ?? []).length === 0 && <p>파싱 결과가 없습니다. 파싱을 먼저 실행하세요.</p>}
          {(doc.articles ?? []).map((art: Article) => (
            <details key={art.id} style={{ marginBottom: 8, border: "1px solid #e5e7eb", borderRadius: 8 }}>
              <summary style={{ padding: "8px 12px", cursor: "pointer", fontWeight: 600 }}>
                {art.article_key} {art.full_title}
              </summary>
              <pre style={{ margin: 0, padding: "12px", background: "#f9fafb", fontSize: 13, whiteSpace: "pre-wrap" }}>
                {art.content}
              </pre>
            </details>
          ))}
        </div>
      )}
    </main>
  );
}
