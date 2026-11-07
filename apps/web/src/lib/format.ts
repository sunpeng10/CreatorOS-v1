export function analysisLabel(analysis: {
  id: string;
  content_title?: string;
  title?: string;
}): string {
  const title = (analysis.content_title || analysis.title || "").trim();
  return title ? `分析·${title}` : `分析 ${analysis.id.slice(0, 8)}`;
}

export function formatMetric(value: unknown): string {
  if (value === null || value === undefined || value === "") return "暂无数据";
  const n = Number(value);
  return Number.isFinite(n)
    ? new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(n)
    : "暂无数据";
}
export function safeExternalUrl(value: unknown): string | null {
  if (typeof value !== "string") return null;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}
export function errorMessage(payload: any): string {
  if (payload?.error?.message) return payload.error.message;
  if (Array.isArray(payload?.detail))
    return payload.detail.map((x: any) => x.msg).join("；");
  if (typeof payload?.detail === "string") return payload.detail;
  return "请求未完成，请检查 API 服务后重试。";
}
export function validateFiles(
  files: { name: string; size: number }[],
): string | null {
  if (files.length > 12) return "每次最多上传 12 个文件。";
  if (files.reduce((sum, file) => sum + file.size, 0) > 100 * 1024 * 1024)
    return "本次素材总大小超过 100 MB，请压缩或分批上传。";
  for (const file of files) {
    if (!/\.(mp4|mov|jpg|jpeg|png|webp|txt|md|srt|vtt)$/i.test(file.name))
      return `${file.name} 是不支持的文件类型。`;
  }
  return null;
}
export function dateLabel(value: unknown): string {
  if (!value) return "尚未记录";
  const d = new Date(String(value));
  return Number.isNaN(d.valueOf())
    ? String(value)
    : d.toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
}
export function money(value: unknown): string {
  return `¥${formatMetric(value ?? 0)}`;
}
export function label(value: unknown): string {
  const labels: Record<string, string> = {
    QUEUED: "排队中",
    RUNNING: "进行中",
    WAITING_APPROVAL: "待审批",
    SUCCEEDED: "已完成",
    FAILED: "失败",
    CANCELED: "已取消",
    NEW: "新线索",
    QUALIFIED: "已沟通",
    PROPOSAL: "已报价",
    WON: "已成交",
    LOST: "已关闭",
    PENDING: "待处理",
    PENDING_APPROVAL: "待审批",
    APPROVED: "已批准",
    REJECTED: "已驳回",
    PAID: "已模拟支付",
    DELIVERED: "已交付",
    COMPLETED: "已完成",
    OPEN: "待处理",
    CLOSED: "已关闭",
    DRAFT: "草稿",
    ACTIVE: "进行中",
    PLANNED: "计划中",
    RESOLVED: "已解决",
    OWNER_ADMIN: "工作区管理员",
    CLIENT_USER: "创作者",
    local: "本地基础分析",
    ai: "MiMo AI 分析",
    mimo: "MiMo AI 分析",
  };
  return labels[String(value)] || String(value ?? "—");
}
