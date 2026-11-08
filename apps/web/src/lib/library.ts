import { api, type Row } from "./api";

type LibraryData = { items: Row[]; total: number };

export async function loadLibrary(path: string): Promise<LibraryData> {
  const items: Row[] = [];
  let total = 0;
  do {
    const page = await api<LibraryData>(
      `${path}?offset=${items.length}&limit=500`,
    );
    total = page.total;
    if (!page.items.length && items.length < total) {
      throw new Error("作品库读取未完成，请刷新后重试。");
    }
    items.push(...page.items);
  } while (items.length < total);
  return { items, total };
}

export function filterLibrary(
  items: Row[],
  filters: {
    query: string;
    platform: string;
    category: string;
    sortOrder: string;
  },
) {
  const keyword = filters.query.trim().toLowerCase();
  return items
    .filter(
      (item) =>
        (!filters.platform ||
          String(item.platform ?? "").trim() === filters.platform) &&
        (!filters.category ||
          String(item.category ?? "").trim() === filters.category) &&
        [item.title, item.author, item.category, item.tags, item.text].some(
          (value) =>
            String(value ?? "")
              .toLowerCase()
              .includes(keyword),
        ),
    )
    .sort((a, b) => {
      const aTime = Date.parse(String(a.collected_at ?? ""));
      const bTime = Date.parse(String(b.collected_at ?? ""));
      if (Number.isNaN(aTime)) return Number.isNaN(bTime) ? 0 : 1;
      if (Number.isNaN(bTime)) return -1;
      return filters.sortOrder === "oldest" ? aTime - bTime : bTime - aTime;
    });
}

const metricLabels = {
  likes: "点赞",
  comments: "评论",
  shares: "分享",
  favorites: "收藏",
  views: "播放量",
};
type MetricKey = keyof typeof metricLabels;
const platformMetrics: Record<string, MetricKey[]> = {
  视频号: ["likes", "comments", "shares"],
  抖音: ["likes", "comments", "shares"],
  B站: ["likes", "favorites", "views", "shares"],
  小红书: ["likes", "comments", "favorites"],
};

export function getLibraryMetrics(item: Row) {
  const platform = String(item.platform ?? "").trim();
  const keys =
    platformMetrics[/^(b站|bilibili)$/i.test(platform) ? "B站" : platform] ??
    (Object.keys(metricLabels) as MetricKey[]);
  return keys.flatMap((key) => {
    const value = item[key] ?? item.metrics?.[key];
    if (
      value == null ||
      String(value).trim() === "" ||
      !Number.isFinite(Number(value))
    )
      return [];
    return [{ key, label: metricLabels[key], value: Number(value) }];
  });
}

export type LibraryImport = { digest: string; name: string; items: Row[] };

export function getLibraryImports(items: Row[]): LibraryImport[] {
  const imports = new Map<string, LibraryImport>();
  for (const item of items) {
    if (!item.file_sha256) continue;
    const digest = String(item.file_sha256);
    const name =
      item.original_filename ||
      String(item.source ?? "").match(/^用户授权导入：(.*) 第 \d+ 行$/)?.[1] ||
      "导入文件";
    if (!imports.has(digest)) imports.set(digest, { digest, name, items: [] });
    imports.get(digest)!.items.push(item);
  }
  return [...imports.values()];
}
