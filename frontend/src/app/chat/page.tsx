"use client";

import { FormEvent, useRef, useState } from "react";
import Link from "next/link";
import { api, ChatResponse } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  text: string;
  context?: string[];
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [topK, setTopK] = useState(5);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const send = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg: Message = { role: "user", text: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res: ChatResponse = await api.chat.query({ query: input, top_k: topK });
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: res.answer, context: res.context },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: `오류: ${e}` },
      ]);
    } finally {
      setLoading(false);
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    }
  };

  return (
    <main style={{ maxWidth: 800, margin: "0 auto", padding: "2rem", display: "flex", flexDirection: "column", height: "100vh" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <h1 style={{ margin: 0 }}>RAG 챗봇</h1>
        <Link href="/">← 문서 목록</Link>
      </div>

      {/* Message list */}
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 12, paddingBottom: "1rem" }}>
        {messages.length === 0 && (
          <p style={{ color: "#9ca3af", textAlign: "center", marginTop: "4rem" }}>
            질문을 입력하면 문서 기반으로 답변합니다.
          </p>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              alignSelf: msg.role === "user" ? "flex-end" : "flex-start",
              maxWidth: "80%",
            }}
          >
            <div
              style={{
                padding: "10px 14px",
                borderRadius: 12,
                background: msg.role === "user" ? "#2563eb" : "#f3f4f6",
                color: msg.role === "user" ? "#fff" : "#111827",
                whiteSpace: "pre-wrap",
              }}
            >
              {msg.text}
            </div>
            {msg.context && msg.context.length > 0 && (
              <details style={{ marginTop: 4 }}>
                <summary style={{ fontSize: 12, color: "#6b7280", cursor: "pointer" }}>
                  참조 컨텍스트 ({msg.context.length}개)
                </summary>
                <ul style={{ margin: "4px 0 0", padding: "0 0 0 16px", fontSize: 12, color: "#6b7280" }}>
                  {msg.context.map((c, j) => (
                    <li key={j}>{c.slice(0, 120)}{c.length > 120 ? "…" : ""}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        ))}
        {loading && (
          <div style={{ alignSelf: "flex-start", color: "#9ca3af", padding: "10px 14px" }}>답변 생성 중…</div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={send} style={{ display: "flex", gap: 8, paddingTop: "0.5rem", borderTop: "1px solid #e5e7eb" }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="질문 입력…"
          style={{ flex: 1, padding: "8px 12px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 15 }}
        />
        <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 13, color: "#6b7280" }}>
          top_k
          <input
            type="number" min={1} max={20} value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            style={{ width: 48, padding: "4px 6px" }}
          />
        </label>
        <button
          type="submit"
          disabled={loading || !input.trim()}
          style={{ padding: "8px 20px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 8, cursor: "pointer" }}
        >
          전송
        </button>
      </form>
    </main>
  );
}
