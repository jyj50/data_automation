import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Data Automation RAG",
  description: "PDF 파싱 & RAG 파이프라인",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
