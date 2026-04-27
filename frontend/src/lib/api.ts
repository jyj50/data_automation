const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------- Types ----------

export interface Document {
  id: number;
  original_filename: string;
  status: string;
  page_count: number;
  selected_page_start: number | null;
  selected_page_end: number | null;
  parse_status: string;
  upsert_status: string;
  question_gen_status: string;
  created_at: string;
  processed_at: string | null;
  error_message: string;
  articles?: Article[];
}

export interface DocumentPage {
  page_number: number;
  has_text: boolean;
  preview_url: string;
  text_clean: string;
}

export interface PagesResponse {
  document_id: number;
  pages: DocumentPage[];
}

export interface Article {
  id: number;
  article_key: string;
  full_title: string;
  content: string;
  chapter_title: string;
  section_title: string;
  source_pages: number[];
  order: number;
  user_edited: boolean;
}

export interface ParseRequest {
  page_start?: number;
  page_end?: number;
  mode?: "hybrid" | "regex" | "llm";
  force_reparse?: boolean;
}

export interface ParseResponse {
  parse_status: string;
  article_count: number;
  warnings: string[];
}

export interface ArticleUpdateRequest {
  full_title?: string;
  content?: string;
  chapter_title?: string;
  section_title?: string;
  order?: number;
}

export interface GenerateQuestionsRequest {
  per_article?: number;
  scope?: "document" | "article";
  article_ids?: number[];
}

export interface ChatRequest {
  query: string;
  top_k?: number;
}

export interface ChatResponse {
  answer: string;
  context: string[];
}

// ---------- Helpers ----------

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

// ---------- API client ----------

export const api = {
  documents: {
    list: (): Promise<Document[]> =>
      apiFetch("/api/documents/"),

    get: (id: number): Promise<Document> =>
      apiFetch(`/api/documents/${id}`),

    upload: (file: File): Promise<Document> => {
      const form = new FormData();
      form.append("file", file);
      return apiFetch("/api/documents/upload/", { method: "POST", body: form });
    },

    pages: (id: number): Promise<PagesResponse> =>
      apiFetch(`/api/documents/${id}/pages/`),

    previewUrl: (id: number, page: number): string =>
      `${API_BASE}/api/documents/${id}/pages/${page}/preview/`,

    parse: (id: number, body: ParseRequest): Promise<ParseResponse> =>
      apiFetch(`/api/documents/${id}/parse/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),

    upsert: (id: number): Promise<Record<string, unknown>> =>
      apiFetch(`/api/documents/${id}/upsert/`, { method: "POST" }),

    generateQuestions: (
      id: number,
      body: GenerateQuestionsRequest,
    ): Promise<{ created: number }> =>
      apiFetch(`/api/documents/${id}/generate-questions/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
  },

  articles: {
    update: (id: number, body: ArticleUpdateRequest): Promise<{ status: string }> =>
      apiFetch(`/api/articles/${id}/`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
  },

  chat: {
    query: (body: ChatRequest): Promise<ChatResponse> =>
      apiFetch("/api/chat/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
  },
};
