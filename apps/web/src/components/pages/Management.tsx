"use client";
import { useState } from "react";
import Link from "next/link";
import {
  Bot,
  Database,
  Download,
  Plus,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { post, rows, useResource, type Row } from "@/lib/api";
import { dateLabel, formatMetric, label, money } from "@/lib/format";
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
  Stat,
  Status,
  type FormField,
} from "../ui";
export function Tickets({ admin = false }: { admin?: boolean }) {
  const r = useResource(admin ? "/admin/tickets" : "/tickets"),
    orders = useResource(admin ? "/admin/orders" : "/orders");
  const [edit, setEdit] = useState<Row | null | "new">(null);
  const fields: FormField[] =
    edit === "new"
      ? [
          { name: "subject", label: "工单主题", required: true },
          {
            name: "description",
            label: "问题描述",
            type: "textarea",
            required: true,
          },
          {
            name: "kind",
            label: "问题类型",
            options: [
              { value: "QUESTION", label: "咨询" },
              { value: "REVISION", label: "修改请求" },
              { value: "COMPLAINT", label: "投诉" },
              { value: "REFUND", label: "退款申请（需要人工审批）" },
            ],
          },
          {
            name: "order_id",
            label: "关联订单",
            options: rows(orders.data).map((o) => ({
              value: o.id,
              label: `${o.id.slice(0, 8)} · ${money(o.amount)}`,
            })),
          },
        ]
      : [
          {
            name: "status",
            label: "处理状态",
            options: admin
              ? [
                  { value: "OPEN", label: "待处理" },
                  { value: "IN_PROGRESS", label: "处理中" },
                  { value: "RESOLVED", label: "已解决" },
                  { value: "CLOSED", label: "已关闭" },
                ]
              : [
                  { value: "OPEN", label: "重开" },
                  { value: "CLOSED", label: "关闭" },
                ],
          },
          {
            name: "reply",
            label: "回复 / 处理记录",
            type: "textarea",
            required: true,
          },
        ];
  return (
    <>
      <PageHeading
        eyebrow="SUPPORT & FEEDBACK"
        title={
          admin ? "让每个问题，都有后续。" : "有问题，留下一条可追踪的记录。"
        }
        description="咨询、修改、投诉与退款申请保留处理记录。真实退款需要人工审批与支付服务配置。"
        action={
          <Button onClick={() => setEdit("new")}>
            <Plus size={16} />
            新建工单
          </Button>
        }
      />
      {r.loading ? (
        <Loading />
      ) : r.error ? (
        <Notice tone="error">{r.error}</Notice>
      ) : null}
      <Card title="工单记录">
        {rows(r.data).length ? (
          <div className="record-list">
            {rows(r.data).map((t) => (
              <div className="record" key={t.id}>
                <div className="grow">
                  <div className="row-actions">
                    <h3>{t.subject}</h3>
                    <Status value={t.status} />
                  </div>
                  <p className="pre-wrap">{t.message || t.description}</p>
                  <small className="muted">
                    {dateLabel(t.created_at)} · {t.kind || "咨询"}
                  </small>
                  {t.reply && <p>处理回复：{t.reply}</p>}
                  <JsonDetails
                    data={t.history || t.logs || t}
                    title="处理日志"
                  />
                </div>
                <Button variant="secondary" onClick={() => setEdit(t)}>
                  {admin ? "处理工单" : "补充记录"}
                </Button>
              </div>
            ))}
          </div>
        ) : (
          <Empty title="目前没有工单">
            需要修改交付报告或反馈问题时，可在这里提交。
          </Empty>
        )}
      </Card>
      {edit && (
        <Modal
          title={edit === "new" ? "创建工单" : "更新工单"}
          close={() => setEdit(null)}
        >
          <DataForm
            fields={fields}
            endpoint={edit === "new" ? "/tickets" : `/tickets/${edit.id}`}
            method={edit === "new" ? "POST" : "PATCH"}
            initial={edit === "new" ? {} : edit}
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

export function Finance() {
  const r = useResource("/admin/finance"),
    weekly = useResource("/admin/weekly-report");
  const d = r.data || {};
  return (
    <>
      <PageHeading
        eyebrow="BUSINESS OBSERVATORY"
        title="看清经营，也看清口径。"
        description="模拟交易、实际收入和模型成本分别展示；每个数字都来自当前组织的业务记录。"
      />
      {r.error && <Notice tone="error">{r.error}</Notice>}
      <div className="stats-grid">
        <Stat
          label="真实收入"
          value={money(d.real_revenue)}
          detail="仅统计真实付款记录"
        />
        <Stat
          label="DEMO 模拟收入"
          value={money(d.demo_revenue)}
          detail="演示数据，不属于实际收入"
        />
        <Stat
          label="模型费用估算"
          value={money(d.model_cost_estimate)}
          detail="以模型供应商账单为准"
        />
        <Stat
          label="真实毛利估算"
          value={money(d.estimated_real_margin)}
          detail="尚未包含人工与其他经营成本"
        />
      </div>
      <div className="two-columns">
        <Card title="客户转化漏斗" subtitle="基于 CRM 状态，不虚构成交或增长">
          <div className="funnel">
            {[
              { key: "leads", name: "提交需求" },
              { key: "qualified", name: "已沟通需求" },
              { key: "proposals", name: "报价阶段" },
              { key: "won", name: "已成交" },
            ].map((f, i) => (
              <div key={f.key}>
                <span className="funnel-number">0{i + 1}</span>
                <b>{f.name}</b>
                <strong>{formatMetric(d.funnel?.[f.key] ?? 0)}</strong>
              </div>
            ))}
          </div>
          <p className="muted mt-4">
            成交率：
            {d.funnel?.conversion_rate == null
              ? "样本不足"
              : `${(d.funnel.conversion_rate * 100).toFixed(1)}%`}
          </p>
        </Card>
        <Card title="费用与支付记录">
          <JsonDetails
            data={{
              payments: d.payments,
              cost_events: d.cost_events,
              demo_refunds: d.demo_refunds,
            }}
            title="查看逐笔记录"
          />
          <p className="muted mt-4">来源：{d.source || "工作区数据库"}</p>
          <Notice tone="warning">
            模型费用只是配置单价下的估算；DEMO 支付不能用作实际收款证明。
          </Notice>
        </Card>
      </div>
      <Card
        title="本周经营复盘"
        subtitle="确定性业务统计，不额外调用付费模型"
        action={
          <Button variant="secondary" onClick={() => void weekly.refresh()}>
            <RefreshCw size={15} />
            更新周报
          </Button>
        }
      >
        {weekly.loading ? (
          <Loading />
        ) : weekly.error ? (
          <Notice tone="error">{weekly.error}</Notice>
        ) : (
          <>
            <p className="muted mb-4">
              生成时间：{dateLabel(weekly.data?.generated_at)}
            </p>
            <pre className="weekly-report">
              {weekly.data?.markdown || JSON.stringify(weekly.data, null, 2)}
            </pre>
            <Button
              variant="secondary"
              className="mt-5"
              onClick={() => {
                const url = URL.createObjectURL(
                  new Blob(
                    [
                      weekly.data?.markdown ||
                        JSON.stringify(weekly.data, null, 2),
                    ],
                    { type: "text/markdown;charset=utf-8" },
                  ),
                );
                const a = document.createElement("a");
                a.href = url;
                a.download = "creatoros-weekly-report.md";
                a.click();
                URL.revokeObjectURL(url);
              }}
            >
              <Download size={16} />
              下载周报
            </Button>
          </>
        )}
      </Card>
      {d.limitations?.length > 0 && (
        <Notice tone="warning">
          <ul>
            {d.limitations.map((s: string, i: number) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </Notice>
      )}
    </>
  );
}

export function Agents() {
  const r = useResource("/admin/agents");
  const [detail, setDetail] = useState<Row | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const items = rows(r.data?.runs || r.data);
  return (
    <>
      <PageHeading
        eyebrow="AGENT OPERATIONS"
        title="每一步协作，都能追溯。"
        description="查看真实任务、阶段交接、模型用量和错误原因。重试只推进失败步骤，保留已完成结果。"
        action={
          <Button variant="secondary" onClick={() => void r.refresh()}>
            <RefreshCw size={16} />
            刷新任务
          </Button>
        }
      />
      {error && <Notice tone="error">{error}</Notice>}
      {r.loading ? (
        <Loading />
      ) : r.error ? (
        <Notice tone="error">{r.error}</Notice>
      ) : null}
      <div className="agent-roster">
        {[
          "COO 调度",
          "内容拆解",
          "数据分析",
          "对标检索",
          "创作策略",
          "报告质检",
          "商务运营",
        ].map((name, i) => (
          <div key={name}>
            <Bot size={19} />
            <span>{name}</span>
            <small>0{i + 1}</small>
          </div>
        ))}
      </div>
      <Card title="任务运行记录">
        {items.length ? (
          <div className="record-list">
            {items.map((a) => (
              <div className="record" key={a.id}>
                <div className="grow">
                  <div className="row-actions">
                    <h3>任务 {a.id.slice(0, 8)}</h3>
                    <Status value={a.status} />
                  </div>
                  <p>
                    预算 {money(a.budget)} · 成本估算 {money(a.cost)} ·{" "}
                    {dateLabel(a.created_at)}
                  </p>
                  {a.error && <p className="error-text">{a.error}</p>}
                  <Link
                    href={`/analyses/${a.analysis_id}`}
                    className="text-link"
                  >
                    关联分析报告
                  </Link>
                </div>
                <Button variant="secondary" onClick={() => setDetail(a)}>
                  查看步骤
                </Button>
                {["FAILED", "CANCELED"].includes(a.status) && (
                  <Button
                    busy={busy}
                    onClick={async () => {
                      setBusy(true);
                      try {
                        await post(`/tasks/${a.id}/retry`);
                        await r.refresh();
                      } catch (e) {
                        setError((e as Error).message);
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    重试
                  </Button>
                )}
              </div>
            ))}
          </div>
        ) : (
          <Empty title="等待第一份分析任务">
            本地与 AI 分析的任务记录会保存在这里。
          </Empty>
        )}
      </Card>
      {r.data?.approvals && (
        <Card title="关联审批">
          <JsonDetails data={r.data.approvals} />
        </Card>
      )}
      {detail && (
        <Modal
          title={`任务 ${detail.id.slice(0, 8)}`}
          close={() => setDetail(null)}
        >
          <AgentDetail id={detail.id} />
        </Modal>
      )}
    </>
  );
}
function AgentDetail({ id }: { id: string }) {
  const r = useResource(`/tasks/${id}`);
  return r.loading ? (
    <Loading />
  ) : r.error ? (
    <Notice tone="error">{r.error}</Notice>
  ) : (
    <div className="stack">
      {rows(r.data?.steps).map((s) => (
        <div key={s.id}>
          <div className="row-actions">
            <h3>{s.name}</h3>
            <Status value={s.status} />
          </div>
          <p className="muted">
            模型：{s.model || "本地"} · Token：{s.tokens ?? 0} · 尝试：
            {s.attempts ?? 0}
          </p>
          {s.error && <Notice tone="error">{s.error}</Notice>}
          <JsonDetails
            data={{ input: s.input, output: s.output }}
            title="输入与输出摘要"
          />
        </div>
      ))}
      <JsonDetails data={r.data?.cost_events} title="模型费用事件" />
    </div>
  );
}

export function DataManagement() {
  const r = useResource("/admin/data");
  const d = r.data || {};
  return (
    <>
      <PageHeading
        eyebrow="DATA & ACCOUNTABILITY"
        title="数据有归属，操作有记录。"
        description="查看当前组织的数据规模、导入来源与操作审计。备份与恢复在本机受控执行。"
      />
      <div className="stats-grid">
        <Stat
          label="内容作品"
          value={formatMetric(d.counts?.contents ?? 0)}
          detail="仅当前管理员组织"
        />
        <Stat
          label="对标资料"
          value={formatMetric(d.counts?.benchmarks ?? 0)}
          detail="来源由录入者提供"
        />
        <Stat
          label="指标快照"
          value={formatMetric(d.counts?.metric_snapshots ?? 0)}
          detail="保留原始导入来源"
        />
        <Stat
          label="导入记录"
          value={rows(d.imports).length}
          detail="按文件内容去重"
        />
      </div>
      {r.error && <Notice tone="error">{r.error}</Notice>}
      <Card title="私有备份与恢复">
        <div className="row-actions">
          <Database size={28} />
          <p>
            {d.backup_instructions ||
              "先停止本项目服务，再同时备份 SQLite 数据库、私有上传文件与配置。恢复前保留现有备份，避免不同时间点的数据混用。"}
          </p>
        </div>
      </Card>
      <Card title="导入状态">
        <JsonDetails data={d.imports || []} title="查看导入文件来源与记录" />
      </Card>
      <Card title="操作审计">
        {rows(d.audit_logs).length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>操作</th>
                  <th>目标记录</th>
                  <th>操作时间</th>
                </tr>
              </thead>
              <tbody>
                {rows(d.audit_logs).map((a) => (
                  <tr key={a.id}>
                    <td>{a.action}</td>
                    <td>
                      <code>{a.target_id || "—"}</code>
                    </td>
                    <td>{dateLabel(a.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty title="暂无审计记录" />
        )}
      </Card>
    </>
  );
}

export function Settings() {
  const me = useResource("/auth/me"),
    ai = useResource("/system/ai-status"),
    analyses = useResource("/analyses");
  const [deletion, setDeletion] = useState(false),
    [message, setMessage] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const user = me.data?.user || me.data || {},
    status = ai.data || {};
  return (
    <>
      <PageHeading
        eyebrow="WORKSPACE SETTINGS"
        title="你的工作区，由你掌握。"
        description="查看身份与模型状态，导出研究资产，追踪任务费用和数据处理申请。"
      />
      <div className="two-columns">
        <Card title="个人与工作区">
          <dl className="profile-dl">
            <dt>用户名称</dt>
            <dd>{user.name || "—"}</dd>
            <dt>邮箱</dt>
            <dd>{user.email || "—"}</dd>
            <dt>角色</dt>
            <dd>{label(user.role)}</dd>
            <dt>组织 ID</dt>
            <dd>
              <code>{user.organization_id || "—"}</code>
            </dd>
          </dl>
        </Card>
        <Card
          title="AI 模型连接"
          action={
            <Button variant="ghost" onClick={() => void ai.refresh()}>
              <RefreshCw size={16} />
              刷新
            </Button>
          }
        >
          <div className="row-actions">
            <Badge tone={status.configured ? "green" : "amber"}>
              {status.configured ? "已配置" : "未配置"}
            </Badge>
            <span>
              {typeof status.connectivity === "string"
                ? status.connectivity
                : "服务状态由后端检测"}
            </span>
          </div>
          <p className="muted mt-4">
            模型：
            {Array.isArray(status.models)
              ? status.models.join(" / ")
              : status.models
                ? Object.values(status.models).join(" / ")
                : "尚未读取"}
          </p>
          <p className="muted mt-3">
            密钥仅保存在服务端配置中。启用 AI
            分析前需单独同意预算；未配置时本地功能正常可用。
          </p>
          {ai.error && <Notice tone="error">{ai.error}</Notice>}
          <JsonDetails data={status} title="安全连接状态详情" />
        </Card>
      </div>
      <Card
        title="数据所有权"
        subtitle="导出属于你的资料；删除申请由管理员审核"
      >
        <div className="row-actions">
          <a className="btn btn-secondary" href="/api/settings/export" download>
            <Download size={16} />
            导出工作区数据
          </a>
          <Button variant="danger" onClick={() => setDeletion(true)}>
            提交数据删除申请
          </Button>
        </div>
        <p className="muted mt-4">
          申请不会立即删除文件。系统保留审批记录，由管理员核对范围并执行受控处理。
        </p>
        {message && <Notice tone="success">{message}</Notice>}
        {error && <Notice tone="error">{error}</Notice>}
      </Card>
      <Card title="任务与费用历史">
        <div className="record-list">
          {rows(analyses.data).map((a) => (
            <Link className="record" key={a.id} href={`/analyses/${a.id}`}>
              <div>
                <h3>
                  {a.content_title || a.title || `分析 ${a.id.slice(0, 8)}`}
                </h3>
                <p>
                  {dateLabel(a.created_at)} · {label(a.mode)} · 估算费用{" "}
                  {a.cost == null ? "报告任务详情可查" : money(a.cost)}
                </p>
              </div>
              <Status value={a.status} />
            </Link>
          ))}
        </div>
        {!rows(analyses.data).length && <Empty title="暂无分析任务" />}
      </Card>
      {deletion && (
        <Modal title="提交数据删除申请" close={() => setDeletion(false)}>
          <form
            method="post"
            className="stack"
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              try {
                await post("/settings/deletion-request", {
                  reason: new FormData(e.currentTarget).get("reason"),
                });
                setMessage("删除申请已进入人工审批；当前数据尚未删除。");
                setDeletion(false);
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <Notice tone="warning">
              请描述你希望删除的数据范围。审批通过并完成受控执行后，删除的数据可能无法恢复。
            </Notice>
            <Field label="删除范围与原因">
              <textarea name="reason" required rows={4} />
            </Field>
            <Button type="submit" variant="danger" busy={busy}>
              <ShieldCheck size={16} />
              提交人工审批
            </Button>
          </form>
        </Modal>
      )}
    </>
  );
}
