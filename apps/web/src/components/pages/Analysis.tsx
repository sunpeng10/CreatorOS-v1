"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowRight,
  Check,
  Download,
  FileText,
  ImageIcon,
  Plus,
  Printer,
  RefreshCw,
  Save,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import { post, rows, useResource, type Row } from "@/lib/api";
import { dateLabel, label, money, validateFiles } from "@/lib/format";
import {
  Badge,
  Button,
  Card,
  Empty,
  Field,
  JsonDetails,
  Loading,
  Notice,
  PageHeading,
  Status,
} from "../ui";
export function Analyze() {
  const router = useRouter();
  const history = useResource("/analyses"),
    accounts = useResource("/accounts"),
    ai = useResource("/system/ai-status");
  const [files, setFiles] = useState<File[]>([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [mode, setMode] = useState("local"),
    [consent, setConsent] = useState(false);
  return (
    <>
      <PageHeading
        eyebrow="CONTENT RESEARCH"
        title="每一份作品，都值得认真研究。"
        description="添加视频、图集或文稿，带着真实创作背景，找到下一步可以验证的方向。"
      />
      <div className="analysis-layout">
        <Card title="新建内容分析" subtitle="01 / 素材与创作背景">
          <form
            method="post"
            className="stack"
            onSubmit={async (e) => {
              e.preventDefault();
              const form = new FormData(e.currentTarget);
              const validation = validateFiles(files);
              if (validation) {
                setError(validation);
                return;
              }
              if (!files.length && !String(form.get("text") || "").trim()) {
                setError("请上传素材或填写作品文稿。");
                return;
              }
              setError("");
              setBusy(true);
              try {
                let content: Row;
                if (files.length) {
                  files.forEach((f) => form.append("files", f));
                  content = await post("/assets/upload", form);
                } else {
                  content = await post("/contents", {
                    title: form.get("title"),
                    text: form.get("text"),
                    kind: "text",
                    platform: form.get("platform"),
                    category: form.get("category"),
                    account_id: form.get("account_id") || null,
                    author: form.get("author"),
                    published_at: form.get("published_at"),
                  });
                }
                const analysis = await post("/analyses", {
                  content_id: content.id,
                  mode,
                });
                if (mode === "ai")
                  await post(`/analyses/${analysis.id}/start`, {
                    confirm_paid: consent,
                    budget: Number(form.get("budget") || 1),
                  });
                router.push(`/analyses/${analysis.id}`);
              } catch (err) {
                setError((err as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <label
              className="dropzone"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                setFiles((old) => [
                  ...old,
                  ...Array.from(e.dataTransfer.files),
                ]);
              }}
            >
              <input
                className="visually-hidden"
                type="file"
                multiple
                accept=".mp4,.mov,.jpg,.jpeg,.png,.webp,.txt,.md,.srt,.vtt"
                onChange={(e) =>
                  setFiles((old) => [
                    ...old,
                    ...Array.from(e.target.files || []),
                  ])
                }
              />
              <span className="upload-icon">
                <Upload size={26} />
              </span>
              <strong>拖放素材到这里，或点击选择</strong>
              <p>视频、图片、文稿与字幕，可一起上传</p>
              <small>
                MP4 / MOV · JPG / PNG / WebP · TXT / MD / SRT / VTT
                <br />
                每次总计最多 100 MB / 12 个文件；视频最多 10 分钟 / 4K
              </small>
            </label>
            {files.length > 0 && (
              <div className="file-list">
                {files.map((f, i) => (
                  <div key={`${f.name}-${i}`}>
                    <FileText size={16} />
                    <span>
                      {f.name}
                      <small>{(f.size / 1024 / 1024).toFixed(2)} MB</small>
                    </span>
                    <button
                      type="button"
                      className="icon-button"
                      aria-label={`移除 ${f.name}`}
                      onClick={() => setFiles(files.filter((_, n) => n !== i))}
                    >
                      <X size={16} />
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="form-grid">
              <Field label="作品标题">
                <input
                  name="title"
                  required
                  maxLength={300}
                  placeholder="为这份研究起一个容易识别的名字"
                />
              </Field>
              <Field label="所属平台">
                <select name="platform">
                  <option value="抖音">抖音</option>
                  <option value="小红书">小红书</option>
                  <option value="B站">B站</option>
                  <option value="视频号">视频号</option>
                  <option value="YouTube">YouTube</option>
                  <option value="其他">其他 / 未发布</option>
                </select>
              </Field>
              <Field label="内容类别">
                <input name="category" placeholder="例如：AI 工具、编程教育" />
              </Field>
              <Field label="关联创作者账号">
                <select name="account_id">
                  <option value="">暂不关联</option>
                  {rows(accounts.data).map((a) => (
                    <option value={a.id} key={a.id}>
                      {a.name} · {a.platform}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="作者 / 账号名">
                <input name="author" placeholder="原始作品作者（可选）" />
              </Field>
              <Field label="发布日期">
                <input name="published_at" type="date" />
              </Field>
            </div>
            <Field
              label="作品文稿 / 字幕 / 创作背景"
              hint="没有字幕的视频可能无法完整判断口播内容。你可以粘贴准确文稿，补充分析依据。"
            >
              <textarea
                name="text"
                maxLength={200000}
                rows={7}
                placeholder="粘贴你的正文、口播稿或字幕，也可以说明目标受众和你最想解决的问题…"
              />
            </Field>
            <div className="form-divider" />
            <div>
              <h3 className="mb-3">02 / 选择研究方式</h3>
              <div className="mode-grid">
                <label
                  className={`mode-card ${mode === "local" ? "selected" : ""}`}
                >
                  <input
                    type="radio"
                    name="analysis_mode"
                    checked={mode === "local"}
                    onChange={() => setMode("local")}
                  />
                  <FileText size={21} />
                  <b>本地基础分析</b>
                  <span>
                    结构统计、媒体解析与基础建议
                    <br />
                    不产生模型调用费用
                  </span>
                </label>
                <label
                  className={`mode-card ${mode === "ai" ? "selected" : ""} ${!ai.data?.configured ? "unavailable" : ""}`}
                >
                  <input
                    type="radio"
                    name="analysis_mode"
                    checked={mode === "ai"}
                    disabled={!ai.data?.configured}
                    onChange={() => setMode("ai")}
                  />
                  <Sparkles size={21} />
                  <b>MiMo 深度分析</b>
                  <span>
                    {ai.data?.configured
                      ? "多 Agent 协作，输出内容策略与脚本"
                      : "AI 未配置 · 本地分析仍可使用"}
                  </span>
                </label>
              </div>
            </div>
            {mode === "ai" && (
              <div className="stack">
                <Notice tone="warning">
                  AI 会将分析所需的素材内容发送至已配置的 MiMo
                  服务。费用按配置单价估算，实际账单以服务商为准；超预算任务会停止。
                </Notice>
                <Field label="本次任务预算上限（元）">
                  <input
                    name="budget"
                    type="number"
                    min="0.01"
                    max="100"
                    step="0.01"
                    defaultValue="1"
                    required
                  />
                </Field>
                <label className="check">
                  <input
                    type="checkbox"
                    required
                    checked={consent}
                    onChange={(e) => setConsent(e.target.checked)}
                  />
                  <span>
                    我同意发送分析所需内容，并在上述预算内调用付费 AI。
                  </span>
                </label>
              </div>
            )}
            {error && <Notice tone="error">{error}</Notice>}
            <Button
              type="submit"
              busy={busy}
              disabled={mode === "ai" && !consent}
            >
              {mode === "ai" ? <Sparkles size={17} /> : <Plus size={17} />}
              {mode === "ai" ? "开始 AI 分析" : "开始本地分析"}
              <ArrowRight size={16} />
            </Button>
          </form>
        </Card>
        <div className="stack">
          <Card title="让分析更有依据">
            <div className="tips-list">
              <div>
                <span>01</span>
                <p>
                  <b>保留作品原貌</b>上传清晰素材，图集按阅读顺序选择。
                </p>
              </div>
              <div>
                <span>02</span>
                <p>
                  <b>补充创作意图</b>你在对谁说话？希望对方记住什么？
                </p>
              </div>
              <div>
                <span>03</span>
                <p>
                  <b>诚实面对缺失</b>缺少播放或转化数据时，不推断作品表现。
                </p>
              </div>
            </div>
          </Card>
          <div className="quiet-panel">
            <ImageIcon size={22} />
            <h3>这是研究，不是内容生成工厂。</h3>
            <p>
              我们支持标题、脚本与策略建议。不提供文生图或视频生成；你始终保留创作判断。
            </p>
          </div>
        </div>
      </div>
      <Card title="分析历史" subtitle="持久保存报告、任务状态与编辑版本">
        {history.loading ? (
          <Loading />
        ) : history.error ? (
          <Notice tone="error">{history.error}</Notice>
        ) : rows(history.data).length ? (
          <div className="record-list">
            {rows(history.data).map((a) => (
              <Link className="record" key={a.id} href={`/analyses/${a.id}`}>
                <div>
                  <h3>
                    {a.title || a.content_title || `分析 ${a.id.slice(0, 8)}`}
                  </h3>
                  <p>
                    {dateLabel(a.created_at)} · {label(a.mode)}
                  </p>
                </div>
                <div className="row-actions">
                  <Status value={a.status} />
                  <ArrowRight size={16} />
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <Empty title="还没有分析记录">
            从上方提交第一份作品，报告将保存在这里。
          </Empty>
        )}
      </Card>
    </>
  );
}

export function AnalysisReport({ id }: { id: string }) {
  const r = useResource(`/analyses/${id}`);
  const content = useResource(
      r.data?.content_id ? `/contents/${r.data.content_id}` : null,
    ),
    versions = useResource(
      r.data?.content_id ? `/contents/${r.data.content_id}/versions` : null,
    );
  const [title, setTitle] = useState(""),
    [script, setScript] = useState(""),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  const data = r.data,
    report = data?.report || {};
  useEffect(() => {
    if (!data) return;
    setTitle(report.titles?.[0] || content.data?.title || "");
    setScript(typeof report.script === "string" ? report.script : "");
  }, [data?.id, report.script, content.data?.title, report.titles, data]);
  useEffect(() => {
    if (
      !data ||
      !["QUEUED", "RUNNING", "WAITING_APPROVAL"].includes(data.status)
    )
      return;
    const t = setInterval(() => void r.refresh(), 2500);
    return () => clearInterval(t);
  }, [data, r.refresh, r]);
  async function taskAction(action: string) {
    setBusy(true);
    setError("");
    try {
      await post(`/tasks/${data.task_id}/${action}`);
      await r.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (r.loading && !data) return <Loading />;
  if (r.error) return <Notice tone="error">{r.error}</Notice>;
  if (!data) return null;
  const steps = rows(data.steps || data.task?.steps || []);
  return (
    <>
      <PageHeading
        eyebrow="CONTENT RESEARCH / REPORT"
        title={content.data?.title || data.title || "内容研究报告"}
        description={`${dateLabel(data.created_at)} · ${label(data.mode)} · 报告 ID ${id.slice(0, 8)}`}
        action={
          <div className="row-actions no-print">
            <a
              className="btn btn-secondary"
              href={`/api/analyses/${id}/export?format=markdown`}
              download
            >
              <Download size={16} />
              Markdown
            </a>
            <a
              className="btn btn-secondary"
              href={`/api/analyses/${id}/export?format=json`}
              download
            >
              JSON
            </a>
            <Button variant="secondary" onClick={() => window.print()}>
              <Printer size={16} />
              打印
            </Button>
          </div>
        }
      />
      <div className="report-status">
        <Status value={data.status} />
        <Badge tone={report.source === "mimo" ? "green" : "neutral"}>
          {label(report.source || data.mode)}
        </Badge>
        {data.task_id && (
          <span className="muted text-sm">
            任务 {data.task_id.slice(0, 8)} · 费用估算{" "}
            {money(data.cost ?? data.task?.cost)}
          </span>
        )}
        <div className="grow" />
        {data.task_id && ["QUEUED", "RUNNING"].includes(data.status) && (
          <Button
            variant="secondary"
            busy={busy}
            onClick={() => taskAction("cancel")}
          >
            取消任务
          </Button>
        )}
        {data.task_id && ["FAILED", "CANCELED"].includes(data.status) && (
          <Button busy={busy} onClick={() => taskAction("retry")}>
            <RefreshCw size={15} />
            从失败步骤重试
          </Button>
        )}
      </div>
      {error && <Notice tone="error">{error}</Notice>}
      {data.error && <Notice tone="error">{data.error}</Notice>}
      {message && <Notice tone="success">{message}</Notice>}
      {!["SUCCEEDED", "FAILED", "CANCELED"].includes(data.status) && (
        <Notice>
          研究任务正在推进，页面会自动更新。已完成的阶段会保留，取消操作可能仍产生正在进行的调用费用。
        </Notice>
      )}
      {steps.length > 0 && (
        <Card title="研究进度" subtitle="每个阶段的状态、重试和输出可追溯">
          <div className="agent-steps">
            {steps.map((s, i) => (
              <div key={s.id || i}>
                <span
                  className={
                    s.status === "SUCCEEDED"
                      ? "step-number complete"
                      : "step-number"
                  }
                >
                  {s.status === "SUCCEEDED" ? <Check size={15} /> : i + 1}
                </span>
                <div>
                  <h3>{s.name}</h3>
                  <Status value={s.status} />
                  <small>
                    重试 {s.attempts ?? 0} · {s.model || "本地确定性处理"}
                  </small>
                  {s.error && <p className="error-text">{s.error}</p>}
                  <JsonDetails
                    data={{ input: s.input, output: s.output }}
                    title="输入与输出"
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
      {content.data?.assets?.length > 0 && (
        <Card title="原始素材" subtitle="私有访问 · 按上传顺序显示">
          <div className="asset-grid">
            {content.data.assets.map((a: Row) => (
              <div key={a.id}>
                {a.mime?.startsWith("image/") ? (
                  <img src={`/api/assets/${a.id}`} alt={a.original_name} />
                ) : a.mime?.startsWith("video/") ? (
                  <video
                    src={`/api/assets/${a.id}`}
                    controls
                    preload="metadata"
                  />
                ) : (
                  <FileText size={28} />
                )}
                <a
                  href={`/api/assets/${a.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {a.original_name}
                </a>
              </div>
            ))}
          </div>
          {content.data.metadata && (
            <JsonDetails
              data={content.data.metadata}
              title="本地媒体解析与元数据"
            />
          )}
        </Card>
      )}
      {Object.keys(report).length > 0 ? (
        <>
          <Card title="研究摘要" subtitle="从可观察的事实出发">
            <p className="report-summary">
              {typeof report.summary === "string"
                ? report.summary
                : JSON.stringify(report.summary)}
            </p>
          </Card>
          <Card
            title="发现与证据"
            subtitle="请将直接观察、数据支持与推测分开理解"
          >
            <div className="findings">
              {(report.findings || []).map((f: any, i: number) => (
                <article key={i}>
                  <div className="finding-index">
                    {String(i + 1).padStart(2, "0")}
                  </div>
                  <div>
                    <div className="row-actions">
                      <h3>{f.label || f.title || "观察"}</h3>
                      <Badge>{f.kind || "直接观察"}</Badge>
                    </div>
                    <p>{f.evidence || f.description || "证据不足"}</p>
                    <div className="row-actions">
                      <Badge>{f.location || f.timecode || "文本 / 全文"}</Badge>
                      <Badge>
                        置信度：{f.confidence ?? "insufficient_data"}
                      </Badge>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </Card>
          <div className="two-columns">
            <Card
              title="标题与开头候选"
              subtitle="建议是起点，请结合真实表达进行修改"
            >
              <h3 className="mb-3">标题方向</h3>
              <ol className="idea-list">
                {(report.titles || []).map((t: string, i: number) => (
                  <li key={i}>{t}</li>
                ))}
              </ol>
              <h3 className="mb-3 mt-6">开头方案</h3>
              <ol className="idea-list">
                {(report.hooks || []).map((t: any, i: number) => (
                  <li key={i}>
                    {typeof t === "string" ? t : JSON.stringify(t)}
                  </li>
                ))}
              </ol>
            </Card>
            <Card
              title="下一步修改清单"
              subtitle="选择一个变量，开始下一次创作实验"
            >
              <ul className="task-list">
                {(report.tasks || []).map((t: any, i: number) => (
                  <li key={i}>
                    <Check size={16} />
                    {typeof t === "string"
                      ? t
                      : t.task || t.description || JSON.stringify(t)}
                  </li>
                ))}
              </ul>
              <Link
                className="btn btn-secondary mt-6"
                href={`/experiments?analysis_id=${id}&content_id=${data.content_id}`}
              >
                创建关联实验
                <ArrowRight size={16} />
              </Link>
            </Card>
          </div>
          <Card
            title="你的创作版本"
            subtitle="修改后保存新版本，原始报告会继续保留"
          >
            <div className="stack">
              <Field label="改进版标题">
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </Field>
              <Field label="完整文本脚本 / 图文结构">
                <textarea
                  rows={14}
                  value={script}
                  onChange={(e) => setScript(e.target.value)}
                />
              </Field>
              <div>
                <Button
                  busy={busy}
                  onClick={async () => {
                    setBusy(true);
                    setError("");
                    try {
                      await post(`/analyses/${id}/versions`, { title, script });
                      setMessage("新版本已保存。");
                      await versions.refresh();
                    } catch (e) {
                      setError((e as Error).message);
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  <Save size={16} />
                  保存为新版本
                </Button>
              </div>
            </div>
            {rows(versions.data).length > 0 && (
              <div className="versions">
                <h3>版本历史</h3>
                {rows(versions.data).map((v) => (
                  <details key={v.id}>
                    <summary>
                      版本 {v.version} · {v.title} · {dateLabel(v.created_at)}
                    </summary>
                    <p className="pre-wrap">{v.script}</p>
                    <Button
                      variant="ghost"
                      onClick={() => {
                        setTitle(v.title || "");
                        setScript(v.script || "");
                      }}
                    >
                      载入此版本继续编辑
                    </Button>
                  </details>
                ))}
              </div>
            )}
          </Card>
          {report.limitations?.length > 0 && (
            <Notice tone="warning">
              <strong>结论边界与缺失信息</strong>
              <ul>
                {report.limitations.map((s: string, i: number) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </Notice>
          )}
        </>
      ) : data.status === "FAILED" ? (
        <Empty title="分析尚未生成报告">
          查看上方错误信息，修正素材或配置后重试。
        </Empty>
      ) : (
        <Empty title="报告将在任务完成后显示">
          本地解析与研究步骤正在保存到工作区。
        </Empty>
      )}
    </>
  );
}
