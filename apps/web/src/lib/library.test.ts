import { describe, expect, it, vi } from "vitest";
import { api } from "./api";
import {
  filterLibrary,
  getLibraryImports,
  getLibraryMetrics,
  loadLibrary,
} from "./library";

vi.mock("./api", () => ({ api: vi.fn() }));

describe("complete library reading", () => {
  it("reads every page instead of truncating at 100 or 500 records", async () => {
    const items = Array.from({ length: 1205 }, (_, i) => ({ id: String(i) }));
    vi.mocked(api).mockReset();
    for (let offset = 0; offset < items.length; offset += 500) {
      vi.mocked(api).mockResolvedValueOnce({
        items: items.slice(offset, offset + 500),
        total: items.length,
      });
    }
    expect(await loadLibrary("/library")).toEqual({ items, total: 1205 });
    expect(api).toHaveBeenLastCalledWith("/library?offset=1000&limit=500");
  });

  it("reports an incomplete response rather than presenting partial data as complete", async () => {
    vi.mocked(api).mockReset().mockResolvedValue({ items: [], total: 200 });
    await expect(loadLibrary("/library")).rejects.toThrow("读取未完成");
  });
});

describe("platform-specific library metrics", () => {
  const metrics = {
    views: 100,
    likes: 0,
    comments: 3,
    shares: 4,
    favorites: 5,
  };
  it.each([
    ["视频号", ["likes", "comments", "shares"]],
    ["抖音", ["likes", "comments", "shares"]],
    ["B站", ["likes", "favorites", "views", "shares"]],
    ["小红书", ["likes", "comments", "favorites"]],
  ])("shows the requested fields for %s", (platform, keys) => {
    expect(
      getLibraryMetrics({ id: "1", platform, metrics }).map((x) => x.key),
    ).toEqual(keys);
  });

  it("omits missing values while preserving measured zero", () => {
    expect(
      getLibraryMetrics({
        id: "1",
        platform: "视频号",
        metrics: {
          views: null,
          likes: 0,
          comments: "",
          shares: null,
        },
      }),
    ).toEqual([{ key: "likes", label: "点赞", value: 0 }]);
  });
});

describe("combined library filters", () => {
  const items = [
    {
      id: "old",
      platform: "B站",
      category: "编程",
      title: "Python",
      author: "甲",
      tags: "教学",
      collected_at: "2026-10-01",
    },
    {
      id: "new",
      platform: "B站",
      category: "编程",
      title: "函数",
      author: "甲",
      tags: ["Python"],
      collected_at: "2026-11-01",
    },
    { id: "missing", platform: "B站", category: "编程", title: "Python" },
    {
      id: "other",
      platform: "小红书",
      category: "编程",
      title: "Python",
      collected_at: "2026-11-02",
    },
  ];

  it("combines keyword, platform, category and collection order without changing source data", () => {
    const original = JSON.stringify(items);
    const filters = {
      query: " PYTHON ",
      platform: "B站",
      category: "编程",
      sortOrder: "newest",
    };
    expect(filterLibrary(items, filters).map((x) => x.id)).toEqual([
      "new",
      "old",
      "missing",
    ]);
    expect(
      filterLibrary(items, { ...filters, sortOrder: "oldest" }).map(
        (x) => x.id,
      ),
    ).toEqual(["old", "new", "missing"]);
    expect(filterLibrary(items, { ...filters, category: "美食" })).toEqual([]);
    expect(JSON.stringify(items)).toBe(original);
  });

  it("searches authors and categories without matching invented missing-field text", () => {
    const filters = {
      query: "甲",
      platform: "",
      category: "",
      sortOrder: "newest",
    };
    expect(filterLibrary(items, filters)).toHaveLength(2);
    expect(filterLibrary(items, { ...filters, query: "编程" })).toHaveLength(4);
    expect(
      filterLibrary(items, { ...filters, query: "undefined" }),
    ).toHaveLength(0);
  });
});

describe("imported file deletion groups", () => {
  it("groups all records by file digest and recovers names from earlier imports", () => {
    const items = [
      { id: "1", file_sha256: "abc", source: "用户授权导入：作品.csv 第 2 行" },
      { id: "2", file_sha256: "abc", source: "用户授权导入：作品.csv 第 3 行" },
      { id: "3", file_sha256: "def", original_filename: "其他.csv" },
      { id: "manual" },
    ];
    expect(getLibraryImports(items)).toEqual([
      { digest: "abc", name: "作品.csv", items: items.slice(0, 2) },
      { digest: "def", name: "其他.csv", items: [items[2]] },
    ]);
  });
});
