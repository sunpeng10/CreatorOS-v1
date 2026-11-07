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
import { api, post, rows, useResource } from "@/lib/api";
import { dateLabel, formatMetric } from "@/lib/format";
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
export function Library() {
  const r = useResource("/library");
  const [query, setQuery] = useState(""),
    [platform, setPlatform] = useState(""),
    [modal, setModal] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [detail, setDetail] = useState<any>(null);
  const items = rows(r.data).filter(
    (x) =>
      (!platform || x.platform === platform) &&
      `${x.title} ${x.author} ${x.category} ${x.tags || ""} ${x.text || ""}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  async function act(fn: () => Promise<any>, msg: string) {
    setBusy(true);
    setError("");
    try {
      await fn();
      setMessage(msg);
      await r.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="REFERENCE LIBRARY"
        title="好的参考，值得被认真保存。"
        description="建立属于你的对标作品库。保留来源、结构与真实数据，研究值得借鉴的表达方式。"
        action={
          <Button onClick={() => setModal(true)}>
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
        <Badge>{rows(r.data).length} 份资料</Badge>
      </div>
      {error && <Notice tone="error">{error}</Notice>}
      {message && <Notice tone="success">{message}</Notice>}
      <div className="toolbar">
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
          {[...new Set(rows(r.data).map((x) => x.platform))].map((x) => (
            <option key={x}>{x}</option>
          ))}
        </select>
        <label className="btn btn-secondary">
          <Upload size={16} />
          导入 CSV
          <input
            className="visually-hidden"
            type="file"
            accept=".csv"
            disabled={busy}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              const fd = new FormData();
              fd.append("file", f);
              void act(
                () => post("/library/import", fd),
                "导入已完成，重复记录由服务端去重。",
              );
              e.target.value = "";
            }}
          />
        </label>
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
          必填：title、platform。建议：url、author、category、tags、text、views、likes、comments、shares、favorites、collected_at。缺失指标留空，不要填
          0；仅导入有权使用的资料。
        </p>
      </details>
      {r.loading ? (
        <Loading />
      ) : r.error ? (
        <Notice tone="error">{r.error}</Notice>
      ) : items.length ? (
        <div className="library-grid">
          {items.map((x, i) => (
            <article className="library-card" key={x.id}>
              <div className={`library-art art-${i % 4}`}>
                <BookOpen size={38} strokeWidth={1.1} />
                <span>{x.category || "内容研究"}</span>
                <span className="art-index">
                  {String(i + 1).padStart(2, "0")}
                </span>
              </div>
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
                <div className="library-metrics">
                  <div>
                    <small>播放量</small>
                    <b>{formatMetric(x.views ?? x.metrics?.views)}</b>
                  </div>
                  <div>
                    <small>点赞</small>
                    <b>{formatMetric(x.likes ?? x.metrics?.likes)}</b>
                  </div>
                </div>
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
                            () => api(`/library/${x.id}`, { method: "DELETE" }),
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
          ))}
        </div>
      ) : (
        <Card>
          <Empty
            title={query ? "没有匹配的作品" : "建立你的第一份参考资料"}
            action={
              <Button onClick={() => setModal(true)}>
                <Plus size={16} />
                手动录入作品
              </Button>
            }
          >
            真实的作品来源，是可信研究的起点。你也可以导入
            CSV，或添加明确标记的演示样本。
          </Empty>
        </Card>
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
