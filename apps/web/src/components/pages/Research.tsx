"use client";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  BarChart3,
  Check,
  FlaskConical,
  Plus,
  Trash2,
  Upload,
  Users,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, post, rows, useResource, type Row } from "@/lib/api";
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
  Stat,
  Status,
  type FormField,
} from "../ui";
const accountFields: FormField[] = [
  { name: "name", label: "账号名称", required: true },
  {
    name: "platform",
    label: "所属平台",
    required: true,
    options: [
      "",
      "抖音",
      "小红书",
      "B站",
      "视频号",
      "快手",
      "微信公众号",
      "微博",
      "YouTube",
      "其他",
    ].map((value) => ({ value, label: value || "请选择平台" })),
  },
  {
    name: "platform_notes",
    label: "其他平台备注",
    placeholder: "选择“其他”时填写实际平台名称",
  },
  {
    name: "category",
    label: "领域 / 内容赛道",
    placeholder: "AI 工具、编程教育…",
  },
  { name: "persona", label: "账号人设" },
  { name: "audience", label: "目标受众", type: "textarea" },
  { name: "style", label: "内容风格", type: "textarea" },
  { name: "url", label: "账号主页", type: "url" },
];

function AccountForm({
  account,
  onDone,
}: {
  account: Row | null;
  onDone: () => void;
}) {
  const [savedId, setSavedId] = useState(account?.id || "");
  const [avatar, setAvatar] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [avatarError, setAvatarError] = useState("");
  useEffect(
    () => () => {
      if (preview) URL.revokeObjectURL(preview);
    },
    [preview],
  );
  const known = accountFields
    .find((field) => field.name === "platform")!
    .options!.some((option) => option.value === account?.platform);
  const initial =
    account && !known
      ? { ...account, platform: "其他", platform_notes: account.platform }
      : account || {};
  const avatarField = (
    <Field label="账号头像" hint="JPG / PNG / WebP，最多 2 MB">
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          minHeight: 46,
        }}
      >
        {(preview || account?.has_avatar) && (
          <img
            width={48}
            height={48}
            style={{ borderRadius: "50%", objectFit: "cover", flexShrink: 0 }}
            src={
              preview ||
              `/api/accounts/${account!.id}/avatar?v=${account!.avatar_version}`
            }
            alt="账号头像预览"
          />
        )}
        <input
          type="file"
          style={{ minWidth: 0, width: "100%" }}
          accept=".jpg,.jpeg,.png,.webp"
          onChange={(event) => {
            const file = event.target.files?.[0] || null;
            if (file && file.size > 2 * 1024 * 1024) {
              setAvatar(null);
              setPreview("");
              setAvatarError("头像最多 2 MB，请换一张图片。");
              return;
            }
            setAvatarError("");
            setAvatar(file);
            setPreview(file ? URL.createObjectURL(file) : "");
          }}
        />
      </div>
    </Field>
  );
  return (
    <DataForm
      fields={accountFields}
      fieldAfter={{ persona: avatarField }}
      initial={initial}
      endpoint={savedId ? `/accounts/${savedId}` : "/accounts"}
      method={savedId ? "PATCH" : "POST"}
      onSaved={async (record) => {
        setSavedId(record.id);
        if (avatarError) throw new Error(avatarError);
        if (avatar) {
          const form = new FormData();
          form.append("file", avatar);
          await post(`/accounts/${record.id}/avatar`, form);
        }
      }}
      onDone={onDone}
    >
      {avatarError && <Notice tone="error">{avatarError}</Notice>}
    </DataForm>
  );
}

export function Accounts() {
  const r = useResource("/accounts");
  const [edit, setEdit] = useState<Row | null | "new">(null);
  return (
    <>
      <PageHeading
        eyebrow="CREATOR PROFILES"
        title="先认识你，再研究内容。"
        description="保存账号定位与受众背景，让每一次分析发生在正确的语境里。"
        action={
          <Button onClick={() => setEdit("new")}>
            <Plus size={17} />
            添加账号
          </Button>
        }
      />
      {r.loading ? (
        <Loading />
      ) : r.error ? (
        <Notice tone="error">{r.error}</Notice>
      ) : rows(r.data).length ? (
        <div className="account-grid">
          {rows(r.data).map((a) => (
            <Card key={a.id}>
              <div className="account-header">
                <span className="account-avatar">
                  {a.has_avatar ? (
                    <img
                      src={`/api/accounts/${a.id}/avatar?v=${a.avatar_version}`}
                      alt={`${a.name}的头像`}
                      style={{
                        width: "100%",
                        height: "100%",
                        objectFit: "cover",
                        borderRadius: "inherit",
                      }}
                    />
                  ) : (
                    a.name.slice(0, 1)
                  )}
                </span>
                <Badge>
                  {a.platform === "其他" && a.platform_notes
                    ? `其他·${a.platform_notes}`
                    : a.platform}
                </Badge>
              </div>
              <h2>{a.name}</h2>
              <p className="muted mt-2">{a.category || "尚未设置内容领域"}</p>
              <dl className="profile-dl">
                <dt>账号人设</dt>
                <dd>{a.persona || "尚未填写"}</dd>
                <dt>目标受众</dt>
                <dd>{a.audience || "尚未填写"}</dd>
                <dt>内容风格</dt>
                <dd>{a.style || "尚未填写"}</dd>
              </dl>
              <div className="row-actions justify-between">
                <ExternalLink url={a.url} />
                <Button variant="secondary" onClick={() => setEdit(a)}>
                  编辑档案
                </Button>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <Empty
            title="创作方向，从你的账号开始"
            action={
              <Button onClick={() => setEdit("new")}>
                <Users size={16} />
                建立账号档案
              </Button>
            }
          >
            无需社交平台登录。手动填写账号定位，后续将作品与指标关联到此账号。
          </Empty>
        </Card>
      )}
      {edit && (
        <Modal
          title={edit === "new" ? "添加创作者账号" : "编辑账号档案"}
          close={() => setEdit(null)}
        >
          <AccountForm
            account={edit === "new" ? null : edit}
            onDone={() => {
              setEdit(null);
              void r.refresh();
            }}
          />
        </Modal>
      )}
    </>
  );
}

const metricFields = [
  "content_id",
  "title",
  "platform",
  "views",
  "likes",
  "comments",
  "shares",
  "favorites",
  "followers",
  "observed_at",
  "source",
];
type MetricImport = { file_sha256: string; name: string; snapshots: number };

export function Analytics() {
  const [denominator, setDenominator] = useState("views"),
    [file, setFile] = useState<File | null>(null),
    [mapping, setMapping] = useState<Record<string, string>>({}),
    [account, setAccount] = useState(""),
    [preview, setPreview] = useState<any>(null),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  const r = useResource(`/analytics/overview?denominator=${denominator}`),
    accounts = useResource("/accounts");
  async function upload(importNow = false) {
    if (!file) return;
    setBusy(true);
    setError("");
    const fd = new FormData();
    fd.append("file", file);
    fd.append("mapping", JSON.stringify(mapping));
    if (account) fd.append("account_id", account);
    try {
      const d = await post(`/metrics/${importNow ? "import" : "preview"}`, fd);
      if (importNow) {
        setMessage(
          `指标已导入。${d.imported ?? d.created ?? ""} ${d.skipped ? `重复跳过 ${d.skipped} 条。` : ""}`,
        );
        setPreview(null);
        await r.refresh();
      } else setPreview(d);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function deleteImport(group: MetricImport) {
    if (
      !window.confirm(
        `删除「${group.name}」导入的 ${group.snapshots} 条指标记录？统计和图表会重新计算，原始作品会保留。`,
      )
    )
      return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await api<{ deleted: number }>(
        `/metrics/imports/${encodeURIComponent(group.file_sha256)}`,
        { method: "DELETE" },
      );
      setMessage(`已删除「${group.name}」的 ${result.deleted} 条指标记录。`);
      await r.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const data = r.data || {},
    items = rows(data.items || data.latest),
    trend = rows(data.trends || data.snapshots),
    imports = (data.imports || []) as MetricImport[];
  return (
    <>
      <PageHeading
        eyebrow="MEASURE WHAT MATTERS"
        title="用真实数据，回看创作选择。"
        description="保留指标来源和观测时间。没有的数据不补零，单次变化不解释为因果。"
      />
      <Card
        title="导入账号指标"
        subtitle="CSV / XLSX · 预览验证后再写入 · 重复记录自动去重"
      >
        <div className="stack">
          <div className="form-grid">
            <Field label="选择指标文件">
              <input
                type="file"
                accept=".csv,.xlsx"
                onChange={(e) => {
                  setFile(e.target.files?.[0] || null);
                  setPreview(null);
                  setMapping({});
                }}
              />
            </Field>
            <Field label="关联账号">
              <select
                value={account}
                onChange={(e) => setAccount(e.target.value)}
              >
                <option value="">暂不关联</option>
                {rows(accounts.data).map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <div className="row-actions">
            <Button
              variant="secondary"
              busy={busy}
              disabled={!file}
              onClick={() => upload()}
            >
              <Upload size={16} />
              预览与验证
            </Button>
            <span className="muted text-sm">
              推荐列：title、views、likes、comments、observed_at；缺失值留空。
            </span>
          </div>
          {preview && (
            <>
              <Notice tone={preview.valid === false ? "warning" : "info"}>
                预览不会保存数据。检查列映射与验证结果后，再确认导入。
              </Notice>
              <details className="mapping-details" open>
                <summary>列映射（系统字段 → 文件列）</summary>
                <div className="mapping-grid">
                  {metricFields.map((f) => (
                    <Field key={f} label={f}>
                      <select
                        value={mapping[f] || ""}
                        onChange={(e) =>
                          setMapping({ ...mapping, [f]: e.target.value })
                        }
                      >
                        <option value="">自动识别</option>
                        {(preview.columns || []).map((c: string) => (
                          <option value={c} key={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </Field>
                  ))}
                </div>
              </details>
              {preview.errors?.length > 0 && (
                <Notice tone="warning">
                  <ul>
                    {preview.errors.slice(0, 10).map((x: any, i: number) => (
                      <li key={i}>
                        {typeof x === "string" ? x : JSON.stringify(x)}
                      </li>
                    ))}
                  </ul>
                </Notice>
              )}
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      {["作品", "观测时间", "播放", "点赞", "评论"].map((s) => (
                        <th key={s}>{s}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows(preview)
                      .slice(0, 8)
                      .map((x, i) => (
                        <tr key={x.id || i}>
                          <td>{x.title || x.content_id || "未提供"}</td>
                          <td>{x.observed_at || "未提供"}</td>
                          <td>{formatMetric(x.views ?? x.metrics?.views)}</td>
                          <td>{formatMetric(x.likes ?? x.metrics?.likes)}</td>
                          <td>
                            {formatMetric(x.comments ?? x.metrics?.comments)}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
              <div className="row-actions">
                <Button
                  variant="secondary"
                  busy={busy}
                  onClick={() => upload()}
                >
                  使用当前映射重新预览
                </Button>
                <Button
                  busy={busy}
                  disabled={preview.valid === false || !rows(preview).length}
                  onClick={() => upload(true)}
                >
                  <Check size={16} />
                  确认导入
                </Button>
              </div>
            </>
          )}
          {error && <Notice tone="error">{error}</Notice>}
          {message && <Notice tone="success">{message}</Notice>}
        </div>
      </Card>
      {imports.length > 0 && (
        <Card
          title="已导入文件"
          subtitle="删除文件对应的指标记录后，统计与图表会同步更新。"
        >
          {imports.map((group) => (
            <div className="library-import-row" key={group.file_sha256}>
              <div>
                <strong>{group.name}</strong>
                <small className="muted">{group.snapshots} 条指标记录</small>
              </div>
              <Button
                variant="ghost"
                disabled={busy || r.loading}
                aria-label={`删除指标文件 ${group.name}`}
                onClick={() => void deleteImport(group)}
              >
                <Trash2 size={16} />
                删除该文件的数据
              </Button>
            </div>
          ))}
        </Card>
      )}
      <div className="toolbar">
        <div className="grow">
          <h2>内容表现</h2>
          <p className="muted text-sm">
            来源：{data.source || "工作区授权导入的指标快照"}
          </p>
        </div>
        <label className="inline-label">
          互动率分母
          <select
            value={denominator}
            onChange={(e) => setDenominator(e.target.value)}
          >
            <option value="views">播放量 views</option>
            <option value="followers">粉丝数 followers</option>
          </select>
        </label>
      </div>
      <Notice>
        {data.engagement_formula ||
          `互动率 = 可用的（点赞 + 评论 + 分享 + 收藏）÷ ${denominator === "views" ? "播放量" : "粉丝数"}。缺少分母时不计算。`}{" "}
        各项缺失指标保留 null。
      </Notice>
      {r.loading ? (
        <Loading />
      ) : r.error ? (
        <Notice tone="error">{r.error}</Notice>
      ) : items.length ? (
        <>
          <div className="stats-grid">
            <Stat
              label="已观测作品"
              value={items.length}
              detail="每份作品的最新快照"
            />
            <Stat
              label="指标快照"
              value={trend.length}
              detail="含历史观测记录"
            />
            <Stat
              label="观测来源"
              value="授权导入"
              detail="原始文件来源保留在记录中"
            />
            <Stat
              label="因果结论"
              value="待验证"
              detail="表现差异不等于修改效果"
            />
          </div>
          <Card
            title="播放表现趋势"
            subtitle={`范围：${trend.length ? `${dateLabel(trend[0].observed_at || trend[0].date)} — ${dateLabel(trend[trend.length - 1].observed_at || trend[trend.length - 1].date)}` : "尚无时间序列"} · 每条为导入快照，非行业平均值`}
          >
            <div className="chart-container">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trend}>
                  <defs>
                    <linearGradient
                      id="viewGradient"
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop
                        offset="0%"
                        stopColor="#0d9488"
                        stopOpacity={0.24}
                      />
                      <stop offset="100%" stopColor="#0d9488" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                    stroke="#e5ebe7"
                  />
                  <XAxis
                    dataKey="observed_at"
                    tickFormatter={(x) => String(x).slice(5, 10)}
                    tick={{ fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="views"
                    name="播放量"
                    stroke="#0d9488"
                    fill="url(#viewGradient)"
                    strokeWidth={2}
                    connectNulls={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card
            title="作品表现排行"
            subtitle="按可用播放指标排序；仅用于本工作区内部比较"
          >
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>作品</th>
                    <th>观测时间</th>
                    <th>播放量</th>
                    <th>点赞</th>
                    <th>评论</th>
                    <th>分享</th>
                    <th>收藏</th>
                    <th>互动率</th>
                  </tr>
                </thead>
                <tbody>
                  {rows(data.rankings || items).map((x, i) => (
                    <tr key={x.id || i}>
                      <td>
                        {x.title || x.content_title || x.content_id}{" "}
                        <Demo value={x.is_demo} />
                      </td>
                      <td>{dateLabel(x.observed_at)}</td>
                      <td>{formatMetric(x.views ?? x.metrics?.views)}</td>
                      <td>{formatMetric(x.likes ?? x.metrics?.likes)}</td>
                      <td>{formatMetric(x.comments ?? x.metrics?.comments)}</td>
                      <td>{formatMetric(x.shares)}</td>
                      <td>{formatMetric(x.favorites)}</td>
                      <td>
                        {x.engagement_rate == null
                          ? "不可计算"
                          : `${(x.engagement_rate * 100).toFixed(2)}%`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          {data.category_comparison && (
            <Card title="类别比较">
              <JsonDetails
                data={data.category_comparison}
                title="查看各类别的样本与指标"
              />
            </Card>
          )}
        </>
      ) : (
        <Card>
          <Empty
            title="让真实的观测数据进入工作区"
            action={
              <span className="muted">
                <BarChart3 size={24} />
              </span>
            }
          >
            从上方导入第一份 CSV 或
            XLSX。图表将使用你的实际指标，不生成演示增长曲线。
          </Empty>
        </Card>
      )}
      {data.limitations?.length > 0 && (
        <Notice tone="warning">
          <ul>
            {data.limitations.map((s: string, i: number) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </Notice>
      )}
    </>
  );
}

export function Experiments() {
  const params = useSearchParams();
  const focusedExperiment = params.get("experiment_id");
  const r = useResource("/experiments"),
    contents = useResource("/contents");
  const [edit, setEdit] = useState<Row | null | "new">(null);
  useEffect(() => {
    if (!focusedExperiment || !r.data) return;
    document.getElementById(`experiment-${focusedExperiment}`)?.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
      block: "center",
    });
  }, [focusedExperiment, r.data]);
  const fields: FormField[] = [
    { name: "title", label: "实验名称", required: true },
    {
      name: "hypothesis",
      label: "待验证假设",
      type: "textarea",
      required: true,
      placeholder: "如果把开头改成具体问题，目标受众是否更愿意继续观看？",
    },
    {
      name: "planned_changes",
      label: "计划修改",
      type: "textarea",
      required: true,
    },
    {
      name: "content_id",
      label: "关联作品",
      options: rows(contents.data).map((c) => ({
        value: c.id,
        label: c.title,
      })),
    },
    {
      name: "analysis_id",
      label: "关联分析 ID",
      defaultValue: params.get("analysis_id") || "",
    },
    { name: "planned_publish_at", label: "预计发布日期", type: "date" },
    {
      name: "observation_window",
      label: "观测窗口",
      placeholder: "发布后 7 天",
    },
    {
      name: "target_metric",
      label: "目标指标",
      options: [
        { value: "views", label: "播放量" },
        { value: "likes", label: "点赞数" },
        { value: "comments", label: "评论数" },
        { value: "shares", label: "分享数" },
        { value: "favorites", label: "收藏数" },
        { value: "followers", label: "粉丝数" },
      ],
    },
    { name: "published_url", label: "后续发布链接", type: "url" },
    { name: "baseline_snapshot_id", label: "基线指标快照 ID" },
    { name: "outcome_snapshot_id", label: "后续指标快照 ID" },
    { name: "outcome_content_id", label: "后续作品 ID" },
    {
      name: "status",
      label: "实验状态",
      options: [
        { value: "PLANNED", label: "计划中" },
        { value: "RUNNING", label: "观测中" },
        { value: "COMPLETED", label: "已复盘" },
      ],
    },
    {
      name: "notes",
      label: "结果与不确定性",
      type: "textarea",
      placeholder: "记录观测结果、样本量、其他同时变化的因素。",
    },
  ];
  return (
    <>
      <PageHeading
        eyebrow="CREATE. OBSERVE. LEARN."
        title="把修改建议，变成创作实验。"
        description="一次聚焦一个假设。保存版本、发布链接与观测窗口，认真记录结果和不确定性。"
        action={
          <Button onClick={() => setEdit("new")}>
            <Plus size={17} />
            创建实验
          </Button>
        }
      />
      <Notice>
        单次增长不能证明因果。尽量固定其他变量，保留观测窗口和样本信息，避免只记录成功案例。
      </Notice>
      {r.loading ? (
        <Loading />
      ) : r.error ? (
        <Notice tone="error">{r.error}</Notice>
      ) : rows(r.data).length ? (
        <div className="experiment-grid">
          {rows(r.data).map((e) => (
            <div
              key={e.id}
              id={`experiment-${e.id}`}
              className={`experiment-entry ${e.id === focusedExperiment ? "experiment-focus" : ""}`}
            >
              <Card>
                <div className="row-actions justify-between">
                  <FlaskConical size={22} />
                  <Status value={e.status} />
                </div>
                <h2 className="mt-6">{e.title}</h2>
                <p className="experiment-hypothesis">
                  {e.hypothesis || "尚未记录假设"}
                </p>
                <dl className="profile-dl">
                  <dt>计划修改</dt>
                  <dd>{e.planned_changes || "尚未填写"}</dd>
                  <dt>目标指标</dt>
                  <dd>{e.target_metric || "尚未填写"}</dd>
                  <dt>观测窗口</dt>
                  <dd>{e.observation_window || "尚未填写"}</dd>
                  <dt>结果</dt>
                  <dd>
                    {e.result?.evidence_status === "observed_difference"
                      ? `观测差异 ${formatMetric(e.result.absolute_change)}；不证明因果`
                      : "数据不足，等待观测与复盘"}
                  </dd>
                </dl>
                {e.notes && <p className="muted pre-wrap mb-4">{e.notes}</p>}
                {e.result && (
                  <JsonDetails data={e.result} title="差异计算与不确定性" />
                )}
                <div className="row-actions justify-between">
                  <ExternalLink url={e.published_url} />
                  <Button variant="secondary" onClick={() => setEdit(e)}>
                    更新实验
                  </Button>
                </div>
              </Card>
            </div>
          ))}
        </div>
      ) : (
        <Card>
          <Empty
            title="下一次修改，就是一次实验"
            action={
              <Button onClick={() => setEdit("new")}>
                <FlaskConical size={16} />
                记录第一个假设
              </Button>
            }
          >
            从你的分析报告出发，提出一个可以观察的变化，逐步积累适合自己的创作方法。
          </Empty>
        </Card>
      )}
      {edit && (
        <Modal
          title={edit === "new" ? "创建创作实验" : "更新实验与复盘"}
          close={() => setEdit(null)}
        >
          <DataForm
            fields={fields}
            endpoint={
              edit === "new" ? "/experiments" : `/experiments/${edit.id}`
            }
            method={edit === "new" ? "POST" : "PATCH"}
            initial={
              edit === "new"
                ? { content_id: params.get("content_id") || "" }
                : edit
            }
            onDone={() => {
              setEdit(null);
              void r.refresh();
            }}
          />
        </Modal>
      )}
    </>
  );
}
