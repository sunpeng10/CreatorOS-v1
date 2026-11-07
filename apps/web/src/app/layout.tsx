import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "CreatorOS · 爆款实验室",
  description:
    "让每一次创作都有数据依据。内容研究、证据分析与创作实验的一体化工作台。",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
