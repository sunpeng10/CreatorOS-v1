"use client";
import Link from "next/link";
import { useState } from "react";
import {
  ArrowRight,
  Check,
  FileText,
  Plus,
  ShieldCheck,
  ShoppingBag,
  Users,
  Wallet,
} from "lucide-react";
import { post, rows, useResource, type Row } from "@/lib/api";
import { dateLabel, formatMetric, money } from "@/lib/format";
import {
  Badge,
  Button,
  Card,
  DataForm,
  Demo,
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
function RecordsLoading({
  resource,
}: {
  resource: ReturnType<typeof useResource>;
}) {
  return resource.loading ? (
    <Loading />
  ) : resource.error ? (
    <Notice tone="error">{resource.error}</Notice>
  ) : null;
}
export function AdminOverview() {
  const r = useResource("/admin/overview");
  const d = r.data || {},
    c = d.counts || d;
  return (
    <>
      <PageHeading
        eyebrow="OWNER COMMAND CENTER"
        title="让创作服务，成为持续运转的业务。"
        description="线索、报价、交付与成本，在一个可以追溯的经营闭环中协同。"
      />
      <RecordsLoading resource={r} />
      <div className="stats-grid">
        <Stat
          label="客户线索"
          value={formatMetric(c.leads ?? 0)}
          detail="来自真实提交的咨询"
          icon={<Users size={18} />}
        />
        <Stat
          label="服务订单"
          value={formatMetric(c.orders ?? 0)}
          detail="报价审批后生成"
          icon={<ShoppingBag size={18} />}
        />
        <Stat
          label="待处理审批"
          value={formatMetric(c.approvals ?? c.pending_approvals ?? 0)}
          detail="由管理员确认下一步"
          icon={<ShieldCheck size={18} />}
        />
        <Stat
          label="模型成本估算"
          value={money(d.model_cost_estimate ?? c.model_cost_estimate ?? 0)}
          detail="按配置单价估算，非实付"
          icon={<Wallet size={18} />}
        />
      </div>
      <div className="workspace-banner">
        <div>
          <span className="eyebrow">FROM FIRST CONTACT TO FIRST DELIVERY</span>
          <h2>
            每一次交付，
            <br />
            都串起真实的业务记录。
          </h2>
          <p>客户线索 → 服务报价 → 人工审批 → Demo 订单 → 报告交付</p>
          <Link href="/admin/leads">
            查看客户线索
            <ArrowRight size={17} />
          </Link>
        </div>
        <ShieldCheck size={110} strokeWidth={0.8} />
      </div>
      <div className="three-columns">
        {[
          {
            href: "leads",
            title: "跟进新需求",
            text: "记录客户问题、跟进备注与下一步。",
            icon: Users,
          },
          {
            href: "approvals",
            title: "审核关键决策",
            text: "报价、退款与数据删除保留人工边界。",
            icon: ShieldCheck,
          },
          {
            href: "orders",
            title: "推进报告交付",
            text: "关联已完成的分析，交付后等待验收。",
            icon: FileText,
          },
        ].map((x) => (
          <Card key={x.href}>
            <x.icon size={24} />
            <h2 className="mt-6">{x.title}</h2>
            <p className="muted mt-3 mb-5">{x.text}</p>
            <Link href={`/admin/${x.href}`} className="text-link">
              进入管理
              <ArrowRight size={15} />
            </Link>
          </Card>
        ))}
      </div>
      <Card title="经营数据明细">
        <JsonDetails data={d} title="查看业务统计口径与数据" />
      </Card>
    </>
  );
}

export function Leads() {
  const r = useResource("/admin/leads");
  const [edit, setEdit] = useState<Row | null>(null);
  const fields: FormField[] = [
    {
      name: "status",
      label: "线索状态",
      options: ["NEW", "QUALIFIED", "PROPOSAL", "WON", "LOST"].map((s) => ({
        value: s,
        label: (
          {
            NEW: "新线索",
            QUALIFIED: "已沟通",
            PROPOSAL: "已报价",
            WON: "已成交",
            LOST: "已关闭",
          } as Record<string, string>
        )[s],
      })),
    },
    { name: "notes", label: "跟进备注", type: "textarea" },
    { name: "next_action", label: "下一步操作" },
  ];
  return (
    <>
      <PageHeading
        eyebrow="CUSTOMER RELATIONSHIPS"
        title="从一个真实需求，开始服务。"
        description="官网咨询会进入这里。记录每次沟通，让报价与交付有明确上下文。"
      />
      <RecordsLoading resource={r} />
      <Card title="客户线索" subtitle={`${rows(r.data).length} 条当前可见记录`}>
        {rows(r.data).length ? (
          <div className="record-list">
            {rows(r.data).map((l) => (
              <div className="record" key={l.id}>
                <div className="grow">
                  <div className="row-actions">
                    <h3>{l.contact}</h3>
                    <Status value={l.status} />
                  </div>
                  <p className="pre-wrap">{l.need}</p>
                  <small className="muted">
                    来源：{l.campaign || "未填写"} · {dateLabel(l.created_at)}
                  </small>
                  {l.notes && <p>跟进：{l.notes}</p>}
                  {l.next_action && <p>下一步：{l.next_action}</p>}
                  <JsonDetails
                    data={l.timeline || l.history || l}
                    title="时间轴与记录"
                  />
                </div>
                <Button variant="secondary" onClick={() => setEdit(l)}>
                  跟进线索
                </Button>
              </div>
            ))}
          </div>
        ) : (
          <Empty title="等待第一份真实咨询">
            官网的需求表单提交后，记录会出现在这里。
          </Empty>
        )}
      </Card>
      {edit && (
        <Modal title={`跟进：${edit.contact}`} close={() => setEdit(null)}>
          <DataForm
            fields={fields}
            endpoint={`/admin/leads/${edit.id}`}
            method="PATCH"
            initial={edit}
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

export function Services() {
  const r = useResource("/admin/services"),
    quotes = useResource("/admin/quotes"),
    leads = useResource("/admin/leads");
  const [edit, setEdit] = useState<Row | null | "new">(null),
    [quote, setQuote] = useState(false);
  const serviceFields: FormField[] = [
    { name: "name", label: "服务名称", required: true },
    {
      name: "price",
      label: "试运营报价（元）",
      type: "number",
      required: true,
    },
    {
      name: "description",
      label: "服务范围与交付内容",
      type: "textarea",
      required: true,
    },
  ];
  const quoteFields: FormField[] = [
    {
      name: "lead_id",
      label: "关联客户线索",
      options: rows(leads.data).map((l) => ({
        value: l.id,
        label: `${l.contact} · ${l.need.slice(0, 35)}`,
      })),
    },
    {
      name: "service_id",
      label: "服务方案",
      options: rows(r.data).map((s) => ({
        value: s.id,
        label: `${s.name} · ${money(s.price)}`,
      })),
    },
    {
      name: "amount",
      label: "本次报价金额（元）",
      required: true,
      type: "number",
    },
    {
      name: "scope",
      label: "确认的服务范围",
      type: "textarea",
      required: true,
    },
    { name: "notes", label: "报价备注", type: "textarea" },
  ];
  return (
    <>
      <PageHeading
        eyebrow="SERVICES & QUOTES"
        title="把服务价值，写成清晰的约定。"
        description="服务价格用于试运营展示。每次客户报价都需要人工审批后，才能创建订单。"
        action={
          <div className="row-actions">
            <Button variant="secondary" onClick={() => setEdit("new")}>
              <Plus size={16} />
              添加服务
            </Button>
            <Button onClick={() => setQuote(true)}>
              <Plus size={16} />
              创建报价
            </Button>
          </div>
        }
      />
      <RecordsLoading resource={r} />
      <div className="three-columns">
        {rows(r.data).map((s) => (
          <Card key={s.id}>
            <Badge>试运营报价</Badge>
            <h2 className="mt-5">{s.name}</h2>
            <div className="service-price">{money(s.price)}</div>
            <p className="muted pre-wrap mb-5">
              {s.description || "尚未填写服务范围"}
            </p>
            <Button variant="secondary" onClick={() => setEdit(s)}>
              编辑服务
            </Button>
          </Card>
        ))}
      </div>
      {!r.loading && !rows(r.data).length && (
        <Card>
          <Empty title="还没有服务方案">
            先定义一个清晰可交付的服务，再根据实际客户需求创建报价。
          </Empty>
        </Card>
      )}
      <Card title="客户报价" subtitle="审批与订单关联保存在同一条业务链中">
        <RecordsLoading resource={quotes} />
        {rows(quotes.data).length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>报价</th>
                  <th>金额</th>
                  <th>服务范围</th>
                  <th>状态</th>
                  <th>创建时间</th>
                  <th>下一步</th>
                </tr>
              </thead>
              <tbody>
                {rows(quotes.data).map((q) => (
                  <tr key={q.id}>
                    <td>
                      <code>{q.id.slice(0, 8)}</code>
                    </td>
                    <td>{money(q.amount)}</td>
                    <td>{q.scope || q.notes || "—"}</td>
                    <td>
                      <Status value={q.status} />
                    </td>
                    <td>{dateLabel(q.created_at)}</td>
                    <td>
                      <Link
                        className="text-link"
                        href={
                          q.status === "APPROVED"
                            ? "/admin/orders"
                            : "/admin/approvals"
                        }
                      >
                        {q.status === "APPROVED" ? "创建订单" : "查看审批"}
                        <ArrowRight size={14} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty title="暂无客户报价" />
        )}
      </Card>
      {edit && (
        <Modal
          title={edit === "new" ? "添加服务" : "编辑服务"}
          close={() => setEdit(null)}
        >
          <DataForm
            fields={serviceFields}
            endpoint={
              edit === "new" ? "/admin/services" : `/admin/services/${edit.id}`
            }
            method={edit === "new" ? "POST" : "PATCH"}
            initial={edit === "new" ? {} : edit}
            onDone={() => {
              setEdit(null);
              void r.refresh();
            }}
          />
        </Modal>
      )}
      {quote && (
        <Modal title="创建报价草案" close={() => setQuote(false)}>
          <Notice>
            提交后生成待审批记录。管理员明确批准后，才可据此创建订单。
          </Notice>
          <DataForm
            fields={quoteFields}
            endpoint="/admin/quotes"
            onDone={() => {
              setQuote(false);
              void quotes.refresh();
            }}
            submit="提交报价审批"
          />
        </Modal>
      )}
    </>
  );
}

export function Approvals() {
  const r = useResource("/approvals");
  const [request, setRequest] = useState(false);
  const [decision, setDecision] = useState<{ item: Row; value: string } | null>(
      null,
    ),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <>
      <PageHeading
        eyebrow="HUMAN IN THE LOOP"
        title="重要的决定，由你确认。"
        description="模型负责建议，管理员负责审批。报价、退款与删除数据等操作保留审核记录。"
        action={
          <Button onClick={() => setRequest(true)}>
            <Plus size={16} />
            发起人工审批
          </Button>
        }
      />
      <RecordsLoading resource={r} />
      {error && <Notice tone="error">{error}</Notice>}
      <Card title="审批记录">
        {rows(r.data).length ? (
          <div className="record-list">
            {rows(r.data).map((a) => (
              <div className="record" key={a.id}>
                <div className="grow">
                  <div className="row-actions">
                    <h3>{a.kind}</h3>
                    <Status value={a.status} />
                  </div>
                  <p>目标记录：{a.target_id || "工作区数据"}</p>
                  <p>
                    {a.reason ||
                      a.description ||
                      "请核对操作范围与关联记录后再决定。"}
                  </p>
                  <small className="muted">{dateLabel(a.created_at)}</small>
                  <JsonDetails data={a} title="完整审批内容" />
                </div>
                {["PENDING", "PENDING_APPROVAL", "WAITING_APPROVAL"].includes(
                  a.status,
                ) && (
                  <div className="row-actions">
                    <Button
                      variant="secondary"
                      onClick={() =>
                        setDecision({ item: a, value: "REJECTED" })
                      }
                    >
                      驳回
                    </Button>
                    <Button
                      onClick={() =>
                        setDecision({ item: a, value: "APPROVED" })
                      }
                    >
                      <Check size={16} />
                      批准
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <Empty title="目前没有待审批事项">
            新的报价或高风险操作请求将显示在这里。
          </Empty>
        )}
      </Card>
      {request && (
        <Modal title="发起关键操作审批" close={() => setRequest(false)}>
          <Notice tone="warning">
            此入口仅创建审批记录。批准后仍需人工在已授权渠道执行，不会自动发布内容或真实付款。
          </Notice>
          <DataForm
            endpoint="/approvals/requests"
            fields={[
              {
                name: "kind",
                label: "操作类型",
                required: true,
                options: [
                  { value: "PUBLISH_CONTENT", label: "对外发布内容" },
                  { value: "REAL_PAYMENT", label: "真实支付" },
                ],
              },
              {
                name: "target_id",
                label: "目标记录 ID",
                required: true,
                hint: "发布填写已完成分析 ID；支付填写已批准报价或待付款订单 ID。",
              },
              {
                name: "reason",
                label: "范围与审批理由",
                required: true,
                type: "textarea",
              },
            ]}
            onDone={() => {
              setRequest(false);
              void r.refresh();
            }}
            submit="提交审批"
          />
        </Modal>
      )}
      {decision && (
        <Modal
          title={`${decision.value === "APPROVED" ? "批准" : "驳回"} ${decision.item.kind}`}
          close={() => setDecision(null)}
        >
          <form
            method="post"
            className="stack"
            onSubmit={async (e) => {
              e.preventDefault();
              const reason = new FormData(e.currentTarget).get("reason");
              setBusy(true);
              setError("");
              try {
                await post(`/approvals/${decision.item.id}/decision`, {
                  decision: decision.value,
                  reason,
                });
                setDecision(null);
                await r.refresh();
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <Notice tone="warning">
              请确认你已核对目标记录与实际影响。此决定将写入审批与审计日志。
            </Notice>
            <Field label="审批意见">
              <textarea
                name="reason"
                required
                rows={4}
                placeholder="记录批准依据或驳回原因"
              />
            </Field>
            <Button type="submit" busy={busy}>
              确认{decision.value === "APPROVED" ? "批准" : "驳回"}
            </Button>
          </form>
        </Modal>
      )}
    </>
  );
}

export function Orders({ admin = false }: { admin?: boolean }) {
  const r = useResource(admin ? "/admin/orders" : "/orders"),
    quotes = useResource(admin ? "/admin/quotes" : null),
    analyses = useResource(admin ? "/analyses" : null);
  const [create, setCreate] = useState(false),
    [delivery, setDelivery] = useState<Row | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  async function action(path: string, body: unknown, success: string) {
    setBusy(true);
    setError("");
    try {
      await post(path, body);
      setMessage(success);
      setDelivery(null);
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
        eyebrow={admin ? "ORDERS & DELIVERY" : "YOUR SERVICE ORDERS"}
        title={admin ? "从确认需求，到完成交付。" : "服务进度，每一步都清楚。"}
        description="订单、支付标记、分析报告与验收记录相互关联。Demo 模拟交易与真实收入严格区分。"
        action={
          admin ? (
            <Button onClick={() => setCreate(true)}>
              <Plus size={17} />
              从报价创建订单
            </Button>
          ) : undefined
        }
      />
      <Notice tone="warning">
        当前仅提供 DEMO
        模拟支付，不能作为实际付款、发票或交易凭证。真实支付服务尚未配置。
      </Notice>
      {error && <Notice tone="error">{error}</Notice>}
      {message && <Notice tone="success">{message}</Notice>}
      <RecordsLoading resource={r} />
      <Card title={admin ? "订单管理" : "我的订单"}>
        {rows(r.data).length ? (
          <div className="record-list">
            {rows(r.data).map((o) => (
              <div className="record order-record" key={o.id}>
                <div className="grow">
                  <div className="row-actions">
                    <h3>{o.title || `服务订单 ${o.id.slice(0, 8)}`}</h3>
                    <Demo value={o.is_demo} />
                    <Status value={o.status} />
                  </div>
                  <p>
                    金额 {money(o.amount)} · 报价 {o.quote_id?.slice(0, 8)} ·{" "}
                    {dateLabel(o.created_at)}
                  </p>
                  {o.delivery?.analysis_id && (
                    <Link
                      href={`/analyses/${o.delivery.analysis_id}`}
                      className="text-link"
                    >
                      打开交付报告
                      <ArrowRight size={14} />
                    </Link>
                  )}
                  {(o.deliveries || []).map((d: Row) => (
                    <Link
                      key={d.id}
                      href={`/analyses/${d.analysis_id}`}
                      className="text-link"
                    >
                      查看报告交付
                      <ArrowRight size={14} />
                    </Link>
                  ))}
                  <JsonDetails data={o} title="订单与交付记录" />
                </div>
                <div className="order-actions">
                  {admin &&
                    ["AWAITING_PAYMENT", "PENDING_PAYMENT", "CREATED"].includes(
                      o.status,
                    ) && (
                      <Button
                        busy={busy}
                        variant="secondary"
                        onClick={() =>
                          action(
                            `/admin/orders/${o.id}/simulate-payment`,
                            {},
                            "DEMO 模拟支付已记录，不代表真实收款。",
                          )
                        }
                      >
                        DEMO 模拟支付
                      </Button>
                    )}
                  {admin && o.status === "PAID" && (
                    <Button onClick={() => setDelivery(o)}>交付分析报告</Button>
                  )}
                  {o.status === "DELIVERED" &&
                    (!admin || !o.customer_organization_id) && (
                      <Button
                        busy={busy}
                        onClick={() =>
                          action(
                            `/orders/${o.id}/accept`,
                            {},
                            "报告已验收，订单完成。",
                          )
                        }
                      >
                        <Check size={16} />
                        确认验收
                      </Button>
                    )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <Empty title="尚未创建服务订单">
            {admin
              ? "先创建报价并完成审批，即可生成一笔可追踪的订单。"
              : "工作区研究功能可直接使用。需要咨询服务时，请从官网提交需求。"}
          </Empty>
        )}
      </Card>
      {create && (
        <Modal title="从已批准报价创建订单" close={() => setCreate(false)}>
          <Notice>本地演示订单会明确标记 DEMO，不会调用真实支付服务。</Notice>
          <DataForm
            endpoint="/admin/orders"
            fields={[
              {
                name: "quote_id",
                label: "选择已批准报价",
                required: true,
                options: rows(quotes.data)
                  .filter((q) => q.status === "APPROVED")
                  .map((q) => ({
                    value: q.id,
                    label: `${q.id.slice(0, 8)} · ${money(q.amount)} · ${q.scope || "服务报价"}`,
                  })),
              },
            ]}
            onDone={() => {
              setCreate(false);
              void r.refresh();
            }}
            submit="创建 DEMO 订单"
          />
        </Modal>
      )}
      {delivery && (
        <Modal title="关联已完成的分析报告" close={() => setDelivery(null)}>
          <form
            method="post"
            className="stack"
            onSubmit={(e) => {
              e.preventDefault();
              void action(
                `/admin/orders/${delivery.id}/deliver`,
                {
                  analysis_id:
                    new FormData(e.currentTarget).get("customer_analysis_id") ||
                    new FormData(e.currentTarget).get("analysis_id"),
                },
                "报告已交付，等待客户验收。",
              );
            }}
          >
            <Field label="待交付分析">
              <select
                name="analysis_id"
                required={!delivery.customer_organization_id}
              >
                <option value="">请选择已完成的报告</option>
                {rows(analyses.data)
                  .filter((a) => a.status === "SUCCEEDED")
                  .map((a) => (
                    <option value={a.id} key={a.id}>
                      {a.content_title || a.title || a.id.slice(0, 8)} ·{" "}
                      {dateLabel(a.created_at)}
                    </option>
                  ))}
              </select>
            </Field>
            <Field
              label="客户报告 ID（关联客户订单必填）"
              hint="粘贴客户工作区中已成功生成的分析 ID。服务端会核对归属，不能交付其他客户的报告。"
            >
              <input
                name="customer_analysis_id"
                required={!!delivery.customer_organization_id}
                placeholder="完整分析 ID，优先于上方选择"
              />
            </Field>
            <Button type="submit" busy={busy}>
              确认交付
            </Button>
          </form>
        </Modal>
      )}
    </>
  );
}
