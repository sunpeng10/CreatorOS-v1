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
  LoaderCircle,
  MoreHorizontal,
  ChevronDown,
  Plus,
  Printer,
  RefreshCw,
  Save,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import { post, rows, useResource, type Row } from "@/lib/api";
import {
  analysisLabel,
  dateLabel,
  label,
  money,
  safeExternalUrl,
  validateFiles,
} from "@/lib/format";
import {
  Badge,
  Button,
  Card,
  DataForm,
  Empty,
  Field,
  JsonDetails,
  Loading,
  Modal,
  Notice,
  PageHeading,
  Status,
} from "../ui";
import { ChineseDateInput, EditableChoice } from "../ContentFields";
import { ReportMedia } from "../ReportMedia";
import { CONTENT_CATEGORIES, CONTENT_PLATFORMS } from "@/lib/content-options";
import artworkStyles from "./AnalysisArtwork.module.css";

function UploadPreview({ file, name }: { file: File; name: string }) {
  const image = /\.(jpe?g|png|webp)$/i.test(file.name);
  const video = /\.(mp4|mov)$/i.test(file.name);
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  useEffect(() => {
    let active = true;
    const preview = image || video ? URL.createObjectURL(file) : "";
    setUrl(preview);
    if (!preview) {
      file
        .slice(0, 4000)
        .text()
        .then(
          (value) => {
            if (active) setText(value);
          },
          () => {
            if (active) setText("暂时无法预览，提交后解析。");
          },
        );
    }
    return () => {
      active = false;
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [file, image, video]);
  return (
    <span className="upload-preview">
      {image ? (
        <img src={url || undefined} alt={name} />
      ) : video ? (
        <video
          src={url || undefined}
          preload="metadata"
          muted
          playsInline
          aria-label={name}
        />
      ) : (
        <span className="upload-preview-text">{text || "正在读取预览…"}</span>
      )}
      <b>{name}</b>
    </span>
  );
}

export function Analyze() {
  const router = useRouter();
  const [historyOffset, setHistoryOffset] = useState(0);
  const history = useResource(`/analyses?limit=30&offset=${historyOffset}`),
    accounts = useResource("/accounts"),
    contentOptions = useResource("/content-options"),
    ai = useResource("/system/ai-status");
  const [files, setFiles] = useState<File[]>([]),
    [title, setTitle] = useState(""),
    [accountName, setAccountName] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [mode, setMode] = useState("local"),
    [consent, setConsent] = useState(false);
  const [menuId, setMenuId] = useState<string | null>(null);
  const [historyAction, setHistoryAction] = useState<{
    kind: "delete" | "note" | "share";
    item: Row;
  } | null>(null);
  const [historyBusy, setHistoryBusy] = useState(false),
    [historyError, setHistoryError] = useState("");
  const categoryOptions = [
    ...new Set([
      ...CONTENT_CATEGORIES,
      ...(contentOptions.data?.categories || []),
    ]),
  ].filter((value) => value !== "其他");
  async function deleteHistory(item: Row) {
    setHistoryBusy(true);
    setHistoryError("");
    try {
      await post(`/analyses/${item.id}`, undefined, "DELETE");
      setHistoryAction(null);
      if (rows(history.data).length === 1 && historyOffset > 0)
        setHistoryOffset(Math.max(0, historyOffset - 30));
      else await history.refresh();
    } catch (error) {
      setHistoryError((error as Error).message);
    } finally {
      setHistoryBusy(false);
    }
  }
  async function shareHistory(item: Row) {
    setHistoryBusy(true);
    setHistoryError("");
    try {
      const response = await fetch(
        `/api/analyses/${item.id}/export?format=markdown`,
        { credentials: "same-origin", cache: "no-store" },
      );
      if (!response.ok)
        throw new Error("暂时无法导出，请确认分析已完成后再试。");
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = `${analysisLabel(item).replace(/[<>:"/\\|?*]/g, "_")}.md`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setHistoryAction(null);
    } catch (error) {
      setHistoryError((error as Error).message);
    } finally {
      setHistoryBusy(false);
    }
  }
  const fileNames = files.map(
    (file, index) =>
      `${title.trim() || "待命名作品"} · 素材 ${index + 1}${file.name.match(/\.[^.]+$/)?.[0].toLowerCase() || ""}`,
  );
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
              if (!title.trim()) {
                setError("请填写作品标题。");
                return;
              }
              form.set("title", title.trim());
              const name =
                accountName.trim() === "暂不关联" ? "" : accountName.trim();
              const matches = rows(accounts.data).filter(
                (item) =>
                  item.name === name ||
                  item.id === name ||
                  `${item.name} · ${item.platform}` === name,
              );
              const account = matches.length === 1 ? matches[0] : undefined;
              form.set("account_id", account?.id || "");
              form.set("account_name", account?.name || name);
              form.set(
                "platform",
                String(form.get("platform") || "").trim() || "未指定",
              );
              form.set(
                "category",
                String(form.get("category") || "").trim() || "未分类",
              );
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
                    account_name: form.get("account_name"),
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
                    allow_web_search: consent,
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
              {files.length ? (
                <span className="upload-previews">
                  {files.map((file, index) => (
                    <UploadPreview
                      key={`${file.name}-${index}`}
                      file={file}
                      name={fileNames[index]}
                    />
                  ))}
                </span>
              ) : (
                <span className="upload-icon">
                  <Upload size={26} />
                </span>
              )}
              <strong>
                {files.length
                  ? `已选择 ${files.length} 份素材，点击继续添加`
                  : "拖放素材到这里，或点击选择"}
              </strong>
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
                      {fileNames[i]}
                      <small>{(f.size / 1024 / 1024).toFixed(2)} MB</small>
                    </span>
                    <button
                      type="button"
                      className="icon-button"
                      aria-label={`移除 ${fileNames[i]}`}
                      onClick={() => setFiles(files.filter((_, n) => n !== i))}
                    >
                      <X size={16} />
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="form-grid analysis-fields">
              <Field label="作品标题">
                <input
                  name="title"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  required
                  maxLength={300}
                />
              </Field>
              <Field label="所属平台">
                <EditableChoice name="platform" options={CONTENT_PLATFORMS} />
              </Field>
              <Field label="内容类别">
                <EditableChoice
                  name="category"
                  options={[...categoryOptions, "其他"]}
                />
              </Field>
              <Field label="关联创作者账号">
                <EditableChoice
                  name="account_name"
                  value={accountName}
                  onChange={(value) =>
                    setAccountName(value === "关联账号" ? "" : value)
                  }
                  options={[
                    "关联账号",
                    "暂不关联",
                    ...new Set(
                      rows(accounts.data).map(
                        (item) => `${item.name} · ${item.platform}`,
                      ),
                    ),
                  ]}
                />
              </Field>
              <Field label="作者 / 账号名">
                <input name="author" />
              </Field>
              <Field label="发布日期">
                <ChineseDateInput />
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
                <Field
                  label="本次任务预算上限（元）"
                  hint="按你填写的金额限制费用，单次最高 10 元；费用为估算，以服务商账单为准。"
                >
                  <input
                    name="budget"
                    type="number"
                    min="0.01"
                    max="10"
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
                    我同意发送分析所需内容，并在上述预算内调用付费 AI
                    识别画面、联网核查公开事实。
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
          <div className={artworkStyles.panel} aria-hidden="true">
            <img
              src="/images/analysis-little-prince.jpg"
              alt=""
              width={897}
              height={1410}
              loading="lazy"
              decoding="async"
            />
          </div>
        </div>
      </div>
      <Card>
        <details className="analysis-history">
          <summary>
            <span>
              <h2>分析历史</h2>
              <small>{history.data?.total || 0} 条记录 · 点击展开或收起</small>
            </span>
            <ChevronDown size={20} />
          </summary>
          {history.loading ? (
            <Loading />
          ) : history.error ? (
            <Notice tone="error">{history.error}</Notice>
          ) : rows(history.data).length ? (
            <div
              className="record-list history-scroll"
              tabIndex={0}
              aria-label="分析历史记录"
            >
              {rows(history.data).map((a) => (
                <div className="record history-item" key={a.id}>
                  <Link className="grow" href={`/analyses/${a.id}`}>
                    <h3>{analysisLabel(a)}</h3>
                    <p>
                      {dateLabel(a.created_at)} · {label(a.mode)}
                    </p>
                    {a.note && <p className="history-note">备注：{a.note}</p>}
                  </Link>
                  <div className="row-actions">
                    <Status value={a.status} />
                    <div
                      className="history-actions"
                      onKeyDown={(event) => {
                        if (event.key === "Escape") setMenuId(null);
                      }}
                      onBlur={(event) => {
                        if (!event.currentTarget.contains(event.relatedTarget))
                          setMenuId(null);
                      }}
                    >
                      <button
                        type="button"
                        className="icon-button"
                        aria-label={`管理${analysisLabel(a)}`}
                        aria-expanded={menuId === a.id}
                        onClick={() => setMenuId(menuId === a.id ? null : a.id)}
                      >
                        <MoreHorizontal size={20} />
                      </button>
                      {menuId === a.id && (
                        <div className="history-menu" role="menu">
                          {(
                            [
                              ["note", "备注"],
                              ["share", "分享"],
                              ["delete", "删除"],
                            ] as const
                          ).map(([kind, text]) => (
                            <button
                              type="button"
                              role="menuitem"
                              key={kind}
                              disabled={
                                kind === "share" && a.status !== "SUCCEEDED"
                              }
                              onClick={() => {
                                setHistoryError("");
                                setMenuId(null);
                                setHistoryAction({ kind, item: a });
                              }}
                            >
                              {text}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <Empty title="还没有分析记录">
              从上方提交第一份作品，报告将保存在这里。
            </Empty>
          )}
          {(history.data?.total || 0) > 30 && (
            <nav
              className="row-actions history-pages"
              aria-label="分析历史分页"
            >
              <Button
                variant="secondary"
                disabled={historyOffset === 0}
                onClick={() =>
                  setHistoryOffset(Math.max(0, historyOffset - 30))
                }
              >
                上一页
              </Button>
              <span>第 {Math.floor(historyOffset / 30) + 1} 页</span>
              <Button
                variant="secondary"
                disabled={historyOffset + 30 >= history.data.total}
                onClick={() => setHistoryOffset(historyOffset + 30)}
              >
                下一页
              </Button>
            </nav>
          )}
        </details>
      </Card>
      {historyAction && (
        <Modal
          title={`${{ note: "分析备注", share: "分享报告", delete: "删除分析记录" }[historyAction.kind]} · ${analysisLabel(historyAction.item)}`}
          close={() => {
            if (!historyBusy) setHistoryAction(null);
          }}
        >
          {historyAction.kind === "note" ? (
            <DataForm
              endpoint={`/analyses/${historyAction.item.id}`}
              method="PATCH"
              fields={[
                {
                  name: "note",
                  label: "备注（最多 3000 字）",
                  type: "textarea",
                },
              ]}
              initial={historyAction.item}
              onDone={() => {
                setHistoryAction(null);
                void history.refresh();
              }}
            />
          ) : (
            <div className="stack">
              <p>
                {historyAction.kind === "share"
                  ? "下载报告文件后，即可通过聊天工具转发给需要查看的人。"
                  : "此操作会将记录移出分析历史，原始素材和费用记录保留。正在进行或已交付的报告无法删除。"}
              </p>
              {historyError && <Notice tone="error">{historyError}</Notice>}
              <div className="row-actions">
                <Button
                  variant="secondary"
                  disabled={historyBusy}
                  onClick={() => setHistoryAction(null)}
                >
                  取消
                </Button>
                <Button
                  busy={historyBusy}
                  onClick={() =>
                    historyAction.kind === "share"
                      ? void shareHistory(historyAction.item)
                      : void deleteHistory(historyAction.item)
                  }
                >
                  {historyAction.kind === "share" ? "下载分享文件" : "删除记录"}
                </Button>
              </div>
            </div>
          )}
        </Modal>
      )}
    </>
  );
}

export function AnalysisReport({ id }: { id: string }) {
  const router = useRouter();
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
  const [previewRefresh, setPreviewRefresh] = useState(false);
  const [selectedTask, setSelectedTask] = useState<number | null>(null);
  const [createdExperiment, setCreatedExperiment] = useState<Row | null>(null);
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
    const t = setInterval(() => void r.refresh(true), 2500);
    return () => clearInterval(t);
  }, [data?.status, r.refresh]);
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
  const identityAdvice = /作者.{0,20}(真实性|资质)|账号资质|身份真实性/;
  const suggestions = (report.tasks || [])
    .map((task: string, index: number) => ({ text: String(task), index }))
    .filter((task: { text: string }) => !identityAdvice.test(task.text));
  const reviews = (report.fact_checks || []).filter(
    (check: Row) => check.status !== "verified",
  );
  const visualAssets = (content.data?.assets || []).some((asset: Row) =>
    /^(image|video)\//.test(asset.mime || ""),
  );
  const mediaReceived =
    report.media_received ??
    !!steps.find((step) => step.name === "content")?.output?.visual_observations
      ?.length;
  const reportNotes = [
    ...(report.media_notes || []),
    ...(data.mode === "local"
      ? ["本地分析未调用模型；识别画面与联网核查请使用 MiMo 深度分析。"]
      : []),
    ...(data.mode === "ai" && visualAssets && !mediaReceived
      ? ["此报告未包含画面识别，请重新识别与核查以更新建议。"]
      : []),
    ...(data.mode === "ai" &&
    ["unavailable", "no_sources"].includes(report.search_status)
      ? ["本次联网核查未完成，相关事实已列入待审阅项。"]
      : []),
    ...(data.mode === "ai" &&
    (!report.search_status || report.search_status === "not_requested")
      ? ["此报告未进行联网核查，可重新识别与核查。"]
      : []),
  ];
  return (
    <>
      <PageHeading
        eyebrow="CONTENT RESEARCH / REPORT"
        title={content.data?.title || data.title || "内容研究报告"}
        description={`${dateLabel(data.created_at)} · ${label(data.mode)} · 报告 ID ${id.slice(0, 8)}`}
        action={
          data.status === "SUCCEEDED" ? (
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
              <Button
                variant="secondary"
                onClick={() => setPreviewRefresh(true)}
              >
                重新识别与核查
              </Button>
            </div>
          ) : undefined
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
        {data.task_id && data.status === "FAILED" && (
          <Button busy={busy} onClick={() => taskAction("retry")}>
            <RefreshCw size={15} />
            从失败步骤重试
          </Button>
        )}
      </div>
      {error && <Notice tone="error">{error}</Notice>}
      {(data.error || data.task?.error) && (
        <Notice tone="error">{data.error || data.task.error}</Notice>
      )}
      {message && <Notice tone="success">{message}</Notice>}
      {data.status === "WAITING_APPROVAL" && (
        <Notice tone="warning">任务已暂停，等待老板后台人工复核。</Notice>
      )}
      {["QUEUED", "RUNNING"].includes(data.status) && (
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
                  {s.status === "SUCCEEDED" ? (
                    <Check size={15} aria-label="运行成功" />
                  ) : s.status === "RUNNING" ? (
                    <LoaderCircle
                      className="spin"
                      size={17}
                      aria-label="正在运行"
                    />
                  ) : (
                    i + 1
                  )}
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
        <ReportMedia
          assets={content.data.assets}
          metadata={content.data.metadata}
        />
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
              {(report.findings || [])
                .filter(
                  (finding: Row) =>
                    !identityAdvice.test(
                      `${finding.label} ${finding.evidence}`,
                    ),
                )
                .map((f: any, i: number) => (
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
                        <Badge>
                          {f.location || f.timecode || "文本 / 全文"}
                        </Badge>
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
                {suggestions.map((task: { text: string; index: number }) => (
                  <li key={task.index}>
                    <label
                      className={`recommended-task ${selectedTask === task.index ? "selected" : ""}`}
                    >
                      <input
                        type="radio"
                        name="recommended_task"
                        checked={selectedTask === task.index}
                        onChange={() => {
                          setSelectedTask(task.index);
                          setCreatedExperiment(null);
                        }}
                      />
                      <span>{task.text}</span>
                      <small>（推荐）</small>
                    </label>
                  </li>
                ))}
              </ul>
              <Button
                variant="secondary"
                className="mt-6"
                busy={busy}
                disabled={selectedTask === null}
                onClick={async () => {
                  setBusy(true);
                  setError("");
                  try {
                    setCreatedExperiment(
                      await post(`/analyses/${id}/experiments`, {
                        task_index: selectedTask,
                      }),
                    );
                  } catch (error) {
                    setError((error as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                创建关联实验
                <ArrowRight size={16} />
              </Button>
              {createdExperiment && (
                <Notice tone="success">
                  实验创建完毕。
                  <Link
                    className="text-link"
                    href={`/experiments?experiment_id=${createdExperiment.id}`}
                  >
                    点击查看
                  </Link>
                </Notice>
              )}
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
          {reviews.length > 0 && (
            <Card
              title="事实核查待审阅"
              subtitle="仅列出查询发现的偏差或未查到可靠依据的事项"
            >
              {reviews.map((check: Row, index: number) => (
                <div className="fact-review" key={index}>
                  <h3>{check.claim}</h3>
                  <p>{check.finding}</p>
                  <p>{check.recommendation}</p>
                  {(check.source_urls || []).map((url: string) => (
                    <a
                      className="text-link"
                      key={url}
                      href={safeExternalUrl(url) || undefined}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {(report.sources || []).find(
                        (source: Row) => source.url === url,
                      )?.title || "查看查询来源"}
                    </a>
                  ))}
                </div>
              ))}
            </Card>
          )}
          {reportNotes.length > 0 && (
            <p className="muted report-footnote">
              {[...new Set(reportNotes)].join(" ")}
            </p>
          )}
        </>
      ) : data.status === "FAILED" ? (
        <Empty title="分析尚未生成报告">
          查看上方错误信息，修正素材或配置后重试。
        </Empty>
      ) : data.status === "CANCELED" ? (
        <Empty title="分析已取消">如需继续研究，请从内容分析页新建任务。</Empty>
      ) : (
        <Empty title="报告将在任务完成后显示">
          本地解析与研究步骤正在保存到工作区。
        </Empty>
      )}
      {previewRefresh && (
        <Modal
          title="重新识别画面与联网核查"
          close={() => {
            if (!busy) setPreviewRefresh(false);
          }}
        >
          <form
            className="stack"
            onSubmit={async (event) => {
              event.preventDefault();
              const form = new FormData(event.currentTarget);
              setBusy(true);
              setError("");
              try {
                const next = await post("/analyses", {
                  content_id: data.content_id,
                  mode: "ai",
                });
                if (next.status !== "SUCCEEDED")
                  await post(`/analyses/${next.id}/start`, {
                    confirm_paid: true,
                    allow_web_search: true,
                    budget: Number(form.get("budget")),
                  });
                setPreviewRefresh(false);
                router.push(`/analyses/${next.id}`);
              } catch (error) {
                setError((error as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <p>
              使用当前素材重新生成创作建议，包含图片/视频识别和公开事件联网核查。旧报告保留。
            </p>
            <Field
              label="本次预算上限（元）"
              hint="单次最高 10 元，含联网调用的费用估算。"
            >
              <input
                name="budget"
                type="number"
                min="0.01"
                max="10"
                step="0.01"
                defaultValue={Math.min(data.task?.budget || 1, 10)}
                required
              />
            </Field>
            <label className="check">
              <input type="checkbox" required />
              <span>
                我同意发送本次分析所需素材，并在上述预算内调用 MiMo 与联网搜索。
              </span>
            </label>
            {error && <Notice tone="error">{error}</Notice>}
            <Button type="submit" busy={busy}>
              确认开始
            </Button>
          </form>
        </Modal>
      )}
    </>
  );
}
