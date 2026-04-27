"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, Document } from "@/lib/api";

export default function HomePage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadDocuments = async () => {
    try {
      setDocuments(await api.documents.list());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await api.documents.upload(file);
      await loadDocuments();
      if (fileRef.current) fileRef.current.value = "";
    } catch (e) {
      setError(String(e));
    } finally {
      setUploading(false);
    }
  };

  return (
    <main style={{ maxWidth: 800, margin: "0 auto", padding: "2rem" }}>
      <h1>문서 목록</h1>

      <form onSubmit={handleUpload} style={{ display: "flex", gap: 8, marginBottom: "2rem" }}>
        <input ref={fileRef} type="file" accept=".pdf" required />
        <button type="submit" disabled={uploading}>
          {uploading ? "업로드 중…" : "PDF 업로드"}
        </button>
      </form>

      {error && <p style={{ color: "red" }}>{error}</p>}
      {loading && <p>로딩 중…</p>}

      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={th}>파일명</th>
            <th style={th}>상태</th>
            <th style={th}>페이지</th>
            <th style={th}>파싱</th>
            <th style={th}>업로드일</th>
          </tr>
        </thead>
        <tbody>
          {documents.map((doc) => (
            <tr key={doc.id}>
              <td style={td}>
                <Link href={`/documents/${doc.id}`}>{doc.original_filename}</Link>
              </td>
              <td style={td}>{doc.status}</td>
              <td style={td}>{doc.page_count}</td>
              <td style={td}>{doc.parse_status}</td>
              <td style={td}>{new Date(doc.created_at).toLocaleString("ko-KR")}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ marginTop: "2rem" }}>
        <Link href="/chat">→ RAG 챗봇 이동</Link>
      </div>
    </main>
  );
}

const th: React.CSSProperties = {
  textAlign: "left",
  padding: "8px 12px",
  borderBottom: "2px solid #e5e7eb",
  background: "#f3f4f6",
};

const td: React.CSSProperties = {
  padding: "8px 12px",
  borderBottom: "1px solid #e5e7eb",
};
