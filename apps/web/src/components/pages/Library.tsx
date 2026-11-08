"use client";
import { useState } from "react";
import {
  BookOpen,
  ExternalLink as ExternalIcon,
  Heart,
  Plus,
  Search,
  Trash2,
  Upload,
} from "lucide-react";
import { api, post, rows, useResource, type Row } from "@/lib/api";
import { CONTENT_PLATFORMS } from "@/lib/content-options";
import { dateLabel, formatMetric, safeExternalUrl } from "@/lib/format";
import {
  filterLibrary,
  getLibraryImports,
  getLibraryMetrics,
  loadLibrary,
  type LibraryImport,
} from "@/lib/library";
import {
  Badge,
  Button,
  Card,
  DataForm,
  Demo,
  Empty,
  ExternalLink,
  Field,
  JsonDetails,
  Loading,
  Modal,
  Notice,
  PageHeading,
} from "../ui";
const libraryFields = [
  { name: "title", label: "真实作品标题", required: true },
  { name: "platform", label: "平台", required: true },
  {
    name: "url",
    label: "原始作品链接",
    type: "url",
    hint: "可留空；仅填写真实、可核验的来源。",
  },
  { name: "author", label: "作者 / 账号", required: true },
  { name: "category", label: "内容类别" },
  { name: "tags", label: "标签（逗号分隔）" },
  { name: "text", label: "内容摘要 / 文稿", type: "textarea" },
  { name: "views", label: "播放量（未知留空）", type: "number" },
  { name: "likes", label: "点赞数（未知留空）", type: "number" },
  { name: "collected_at", label: "采集日期", type: "date" },
];

function LibraryCover({ item, index }: { item: Row; index: number }) {
  const [failedUrl, setFailedUrl] = useState("");
  const coverUrl = item.cover_version
    ? `/api/library/${encodeURIComponent(item.id)}/cover?v=${encodeURIComponent(item.cover_version)}`
    : safeExternalUrl(item.cover_url);
  const showCover = Boolean(coverUrl && coverUrl !== failedUrl);
  return (
    <div
      className={`library-art ${showCover ? "has-cover" : `art-${index % 4}`}`}
    >
      {showCover ? (
        <img
          src={coverUrl!}
          alt={`${item.title}的封面`}
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          onError={() => setFailedUrl(coverUrl!)}
        />
      ) : (
        <>
          <BookOpen size={38} strokeWidth={1.1} />
          <span>{item.category || "内容研究"}</span>
        </>
      )}
      <span className="art-index">{String(index + 1).padStart(2, "0")}</span>
    </div>
  );
}

export function Library() {
  const r = useResource("/library", 0, loadLibrary);
  const [query, setQuery] = useState(""),
    [platform, setPlatform] = useState(""),
    [category, setCategory] = useState(""),
    [sortOrder, setSortOrder] = useState("newest"),
    [modal, setModal] = useState(false),
    [importModal, setImportModal] = useState(false),
    [deletingImport, setDeletingImport] = useState<{
      digest: string;
      removed: number;
    } | null>(null),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [detail, setDetail] = useState<any>(null);
  const allItems = rows(r.data);
  const keyword = query.trim().toLowerCase();
  const hasFilters = Boolean(keyword || platform || category);
  const items = filterLibrary(allItems, {
    query,
    platform,
    category,
    sortOrder,
  });
  const imports = getLibraryImports(allItems);
  const platforms = [
    ...new Set([
      ...CONTENT_PLATFORMS,
      ...allItems
        .map((item) => String(item.platform || "").trim())
        .filter(Boolean),
    ]),
  ];
  const categories = [
    ...new Set(
      allItems
        .map((item) => String(item.category ?? "").trim())
        .filter(Boolean),
    ),
  ];
  function clearFilters() {
    setQuery("");
    setPlatform("");
    setCategory("");
    setSortOrder("newest");
  }
  async function act(
    fn: () => Promise<any>,
    msg: string | ((result: any) => string),
  ) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await fn();
      setMessage(typeof msg === "function" ? msg(result) : msg);
      await r.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function deleteImport(group: LibraryImport) {
    if (
      !window.confirm(
        `删除「${group.name}」导入的 ${group.items.length} 份作品及其上传封面？只移除工作区记录，电脑上的原文件会保留。`,
      )
    )
      return;
    await act(async () => {
      let removed = 0;
      setDeletingImport({ digest: group.digest, removed });
      try {
        for (const item of group.items) {
          await api(`/library/${item.id}`, { method: "DELETE" });
          removed += 1;
          setDeletingImport({ digest: group.digest, removed });
        }
      } catch (e) {
        await r.refresh();
        throw new Error(
          `已删除 ${removed} / ${group.items.length} 份作品，其余记录保留。${(e as Error).message}`,
        );
      } finally {
        setDeletingImport(null);
      }
    }, `已删除「${group.name}」导入的 ${group.items.length} 份作品。`);
  }
  return (
    <>
      <PageHeading
        eyebrow="REFERENCE LIBRARY"
        title="好的参考，值得被认真保存。"
        description="建立属于你的对标作品库。保留来源、结构与真实数据，研究值得借鉴的表达方式。"
        action={
          <Button disabled={busy} onClick={() => setModal(true)}>
            <Plus size={17} />
            录入作品
          </Button>
        }
      />
      <div className="library-intro">
        <BookOpen size={25} />
        <div>
          <h3>你的研究资料，由你掌握来源。</h3>
          <p>
            手动添加或导入你有权使用的作品资料。演示样本始终单独标记，不视为真实热门作品。
          </p>
        </div>
        <Badge>{allItems.length} 份资料</Badge>
      </div>
      {error && !importModal && <Notice tone="error">{error}</Notice>}
      {message && <Notice tone="success">{message}</Notice>}
      <div
        className="toolbar library-toolbar"
        role="group"
        aria-label="作品筛选与排序"
      >
        <label className="search-input">
          <Search size={17} />
          <input
            aria-label="搜索作品"
            placeholder="搜索标题、作者、类别或标签…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <select
          aria-label="筛选平台"
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
        >
          <option value="">全部平台</option>
          {platforms.map((x) => (
            <option key={x}>{x}</option>
          ))}
        </select>
        <select
          aria-label="筛选内容类别"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          <option value="">全部类别</option>
          {categories.map((x) => (
            <option key={x}>{x}</option>
          ))}
        </select>
        <select
          aria-label="采集时间排序"
          value={sortOrder}
          onChange={(e) => setSortOrder(e.target.value)}
        >
          <option value="newest">最新采集</option>
          <option value="oldest">最早采集</option>
        </select>
        <Button
          type="button"
          variant="secondary"
          disabled={!query && !platform && !category && sortOrder === "newest"}
          onClick={clearFilters}
        >
          清除筛选
        </Button>
        <Button
          variant="secondary"
          disabled={busy}
          onClick={() => {
            setError("");
            setImportModal(true);
          }}
        >
          <Upload size={16} />
          导入 CSV
        </Button>
        <Button
          variant="ghost"
          busy={busy}
          onClick={() =>
            act(() => post("/library/demo"), "演示样本已明确标记为 DEMO。")
          }
        >
          添加 Demo 样本
        </Button>
      </div>
      <details className="import-help">
        <summary>CSV 文件需要哪些列？</summary>
        <p>
          必填：title、platform。建议：url、author、category、tags、text、views、likes、comments、shares、favorites、collected_at。可选封面：cover_path（本机图片路径或文件名，导入时同时选择图片）或
          cover_url（图片网址）。支持 JPG、PNG、WebP。缺失指标留空，不要填
          0；仅导入有权使用的资料。
        </p>
      </details>
      {!r.loading && !r.error && imports.length > 0 && (
        <details className="library-imports" open>
          <summary>已导入文件（{imports.length}）</summary>
          {imports.map((group) => (
            <div className="library-import-row" key={group.digest}>
              <div>
                <strong>{group.name}</strong>
                <small className="muted">{group.items.length} 份作品</small>
              </div>
              <Button
                variant="ghost"
                disabled={busy}
                aria-label={`删除导入文件 ${group.name}`}
                onClick={() => void deleteImport(group)}
              >
                <Trash2 size={16} />
                {deletingImport?.digest === group.digest
                  ? `删除中 ${deletingImport.removed} / ${group.items.length}`
                  : "删除该文件的作品"}
              </Button>
            </div>
          ))}
        </details>
      )}
      {!r.loading && !r.error && (
        <p className="muted text-sm mb-4" role="status">
          显示 {items.length} / {allItems.length} 份作品
        </p>
      )}
      {r.loading ? (
        <Loading />
      ) : r.error ? (
        <Notice tone="error">{r.error}</Notice>
      ) : items.length ? (
        <div className="library-grid">
          {items.map((x, i) => {
            const metrics = getLibraryMetrics(x);
            return (
              <article className="library-card" key={x.id}>
                <LibraryCover item={x} index={i} />
                <div className="library-card-body">
                  <div className="row-actions">
                    <Badge>{x.platform}</Badge>
                    <Demo value={x.is_demo} />
                  </div>
                  <button className="title-button" onClick={() => setDetail(x)}>
                    {x.title}
                  </button>
                  <p>
                    {x.author || "作者未提供"} · {x.category || "未分类"}
                  </p>
                  {metrics.length > 0 && (
                    <div className="library-metrics">
                      {metrics.map((metric) => (
                        <div key={metric.key}>
                          <small>{metric.label}</small>
                          <b>{formatMetric(metric.value)}</b>
                        </div>
                      ))}
                    </div>
                  )}
                  <small className="muted">
                    采集 / 更新：{dateLabel(x.collected_at || x.updated_at)}
                  </small>
                  <footer>
                    <ExternalLink url={x.url} />
                    <div className="row-actions">
                      <Button
                        variant="ghost"
                        aria-label="收藏作品"
                        busy={busy}
                        onClick={() =>
                          act(
                            () => post(`/library/${x.id}/favorite`),
                            "收藏状态已更新。",
                          )
                        }
                      >
                        <Heart
                          size={17}
                          fill={x.favorite ? "currentColor" : "none"}
                        />
                      </Button>
                      <Button
                        variant="ghost"
                        aria-label="删除作品"
                        busy={busy}
                        onClick={() => {
                          if (
                            window.confirm(
                              `删除对标记录「${x.title}」？此操作仅移除工作区中的这条记录。`,
                            )
                          )
                            void act(
                              () =>
                                api(`/library/${x.id}`, { method: "DELETE" }),
                              "作品记录已删除。",
                            );
                        }}
                      >
                        <Trash2 size={16} />
                      </Button>
                    </div>
                  </footer>
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <Card>
          <Empty
            title={hasFilters ? "没有匹配的作品" : "建立你的第一份参考资料"}
            action={
              hasFilters ? (
                <Button variant="secondary" onClick={clearFilters}>
                  清除筛选
                </Button>
              ) : (
                <Button onClick={() => setModal(true)}>
                  <Plus size={16} />
                  手动录入作品
                </Button>
              )
            }
          >
            {hasFilters
              ? "试试调整平台、内容类别或关键词，也可以清除筛选查看全部作品。"
              : "真实的作品来源，是可信研究的起点。你也可以导入 CSV，或添加明确标记的演示样本。"}
          </Empty>
        </Card>
      )}
      {importModal && (
        <Modal
          title="导入 CSV 与封面"
          close={() => {
            if (!busy) setImportModal(false);
          }}
        >
          <form
            method="post"
            className="stack"
            onSubmit={(e) => {
              e.preventDefault();
              const fd = new FormData(e.currentTarget);
              const covers = fd
                .getAll("covers")
                .filter((file) => file instanceof File && file.size > 0);
              fd.delete("covers");
              covers.forEach((file) => fd.append("covers", file));
              void act(
                async () => {
                  const result = await post("/library/import", fd);
                  setImportModal(false);
                  return result;
                },
                (result) =>
                  `导入完成：新增 ${result.imported} 份，已存在 ${result.duplicates} 份，匹配封面 ${result.covers_imported ?? 0} 张。${result.missing_covers ? `有 ${result.missing_covers} 条封面未匹配，可补选图片后重新导入。` : ""}`,
              );
            }}
          >
            <Field label="CSV 文件">
              <input
                name="file"
                type="file"
                accept=".csv"
                required
                disabled={busy}
              />
            </Field>
            <Field
              label="封面图片（可选，可多选）"
              hint="CSV 的 cover_path / 照片列填写图片文件名或本机路径，并在这里选择对应的 JPG、PNG、WebP 图片。没有封面列可直接导入。"
            >
              <input
                name="covers"
                type="file"
                accept=".jpg,.jpeg,.png,.webp"
                multiple
                disabled={busy}
              />
            </Field>
            {error && <Notice tone="error">{error}</Notice>}
            <Button type="submit" busy={busy}>
              <Upload size={16} />
              开始导入
            </Button>
          </form>
        </Modal>
      )}
      {modal && (
        <Modal title="录入对标作品" close={() => setModal(false)}>
          <DataForm
            fields={libraryFields}
            endpoint="/library"
            onDone={() => {
              setModal(false);
              void r.refresh();
            }}
            submit="保存作品"
          />
        </Modal>
      )}
      {detail && (
        <Modal title={detail.title} close={() => setDetail(null)}>
          <div className="stack">
            <div className="row-actions">
              <Badge>{detail.platform}</Badge>
              <Demo value={detail.is_demo} />
            </div>
            <p className="pre-wrap">
              {detail.text || detail.description || "未提供内容摘要。"}
            </p>
            <ExternalLink url={detail.url}>
              打开原始来源
              <ExternalIcon size={14} />
            </ExternalLink>
            <JsonDetails data={detail} title="指标来源与完整记录" />
          </div>
        </Modal>
      )}
    </>
  );
}

export function Recommendations() {
  const contents = useResource("/contents");
  const [result, setResult] = useState<any>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <>
      <PageHeading
        eyebrow="DISCOVER WITH CONTEXT"
        title="找到相关参考，而不只是高播放。"
        description="从你的作品库中，结合主题相似度、类别与可用表现指标寻找参考。每一次推荐都解释理由。"
      />
      <Card
        title="你正在研究什么？"
        subtitle="推荐仅使用当前工作区已录入的资料"
      >
        <form
          method="post"
          className="stack"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            const f = new FormData(e.currentTarget);
            try {
              setResult(
                await post("/recommendations/search", {
                  query: f.get("query"),
                  content_id: f.get("content_id") || null,
                  limit: Number(f.get("limit")),
                  include_demo: f.get("include_demo") === "on",
                }),
              );
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <Field label="主题 / 创作问题">
            <input
              name="query"
              required
              placeholder="例如：如何向编程初学者解释 AI Agent？"
            />
          </Field>
          <div className="form-grid">
            <Field label="关联自己的作品">
              <select name="content_id">
                <option value="">暂不关联</option>
                {rows(contents.data).map((c) => (
                  <option value={c.id} key={c.id}>
                    {c.title}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="推荐数量">
              <select name="limit" defaultValue="5">
                {[3, 5, 10].map((n) => (
                  <option value={n} key={n}>
                    Top {n}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <label className="check">
            <input name="include_demo" type="checkbox" />
            <span>包含明确标记的 Demo 样本（仅用于流程演示）</span>
          </label>
          {error && <Notice tone="error">{error}</Notice>}
          <div>
            <Button busy={busy} type="submit">
              <Search size={17} />
              查找相关作品
            </Button>
          </div>
        </form>
      </Card>
      {result === null ? (
        <div className="quiet-panel">
          <h3>相似，不等于表现更好。</h3>
          <p>
            相似度表示内容相关性；相对表现基于同作者样本的播放中位数。样本不足时，会明确显示不可计算。
          </p>
        </div>
      ) : rows(result).length ? (
        <div className="stack">
          {rows(result).map((r, i) => {
            const x = r.benchmark || r.item || r;
            return (
              <Card key={r.id || x.id || i}>
                <div className="recommendation">
                  <div className="recommendation-rank">
                    {String(i + 1).padStart(2, "0")}
                  </div>
                  <div className="grow">
                    <div className="row-actions">
                      <Badge>{x.platform}</Badge>
                      <Demo value={x.is_demo} />
                    </div>
                    <h2 className="mt-3">{x.title}</h2>
                    <p className="muted">
                      {x.author || "作者未提供"} · 采样{" "}
                      {dateLabel(x.collected_at || x.created_at)}
                    </p>
                    <div className="recommendation-scores">
                      <div>
                        <span>内容相似度</span>
                        <b>
                          {r.similarity == null
                            ? "不可计算"
                            : `${Math.round(r.similarity * 100)}%`}
                        </b>
                      </div>
                      <div>
                        <span>相对播放表现</span>
                        <b>
                          {r.relative_performance == null
                            ? "样本不足"
                            : `${Number(r.relative_performance).toFixed(2)}×`}
                        </b>
                      </div>
                      <div>
                        <span>数据完备度</span>
                        <b>
                          {r.data_completeness == null
                            ? "未知"
                            : `${Math.round(r.data_completeness * 100)}%`}
                        </b>
                      </div>
                    </div>
                    <ul className="idea-list">
                      {(r.reasons || []).map((reason: string, n: number) => (
                        <li key={n}>{reason}</li>
                      ))}
                    </ul>
                    <p className="muted text-sm mt-3">
                      借鉴结构和表达思路；请独立创作，不直接复制原文、画面或未经授权素材。
                    </p>
                    <ExternalLink url={x.url} />
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      ) : (
        <Card>
          <Empty title="当前作品库还没有合适的参考">
            先添加与你的主题相关的真实作品，或明确选择包含 Demo 样本后体验流程。
          </Empty>
        </Card>
      )}
    </>
  );
}
