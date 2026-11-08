"use client";
import { useEffect, useState } from "react";
import { FileText, Maximize2 } from "lucide-react";
import { type Row } from "@/lib/api";
import { Card, JsonDetails, Modal } from "./ui";

function mediaKind(asset: Row) {
  if (
    asset.mime?.startsWith("image/") ||
    /\.(jpe?g|png|webp)$/i.test(asset.original_name || "")
  )
    return "image";
  if (
    asset.mime?.startsWith("video/") ||
    /\.(mp4|mov)$/i.test(asset.original_name || "")
  )
    return "video";
  return "text";
}

export function ReportMedia({
  assets,
  metadata,
}: {
  assets: Row[];
  metadata?: unknown;
}) {
  const [active, setActive] = useState<Row | null>(null);
  const [failed, setFailed] = useState<Record<string, boolean>>({});
  useEffect(() => {
    if (!active) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setActive(null);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [active]);
  function render(asset: Row) {
    const url = `/api/assets/${asset.id}`;
    const poster = asset.keyframes?.[0]?.asset_id
      ? `/api/assets/${asset.keyframes[0].asset_id}`
      : undefined;
    if (mediaKind(asset) === "image")
      return (
        <img
          src={url}
          alt={asset.original_name}
          onError={() => setFailed((old) => ({ ...old, [asset.id]: true }))}
        />
      );
    if (mediaKind(asset) === "video")
      return (
        <video
          key={asset.id}
          src={url}
          poster={poster}
          controls
          playsInline
          preload="metadata"
          onError={() => setFailed((old) => ({ ...old, [asset.id]: true }))}
        />
      );
    return <FileText size={28} />;
  }
  return (
    <>
      <Card title="原始素材" subtitle="私有访问 · 按上传顺序显示">
        <div className="asset-grid">
          {assets
            .filter(
              (asset) =>
                asset.role !== "keyframe" && asset.data?.role !== "keyframe",
            )
            .map((asset) => (
              <div key={asset.id} className="media-tile">
                {render(asset)}
                {mediaKind(asset) !== "text" && (
                  <button
                    className="media-expand"
                    type="button"
                    aria-label={`放大查看${asset.original_name}`}
                    onClick={() => setActive(asset)}
                  >
                    <Maximize2 size={17} />
                  </button>
                )}
                {failed[asset.id] && (
                  <p className="muted text-sm">
                    无法预览时，可打开原文件查看；视频编码需浏览器支持。
                  </p>
                )}
                <a
                  href={`/api/assets/${asset.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {asset.original_name}
                </a>
              </div>
            ))}
        </div>
        {metadata != null && (
          <JsonDetails data={metadata} title="本地媒体解析与元数据" />
        )}
      </Card>
      {active && (
        <Modal
          title={active.original_name || "素材预览"}
          className="media-preview-modal"
          close={() => setActive(null)}
        >
          <div className="media-preview-content">{render(active)}</div>
          {failed[active.id] && (
            <p className="muted">预览不可用，请通过原文件链接查看。</p>
          )}
        </Modal>
      )}
    </>
  );
}
