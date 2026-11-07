"use client";
import {
  Fragment,
  type ButtonHTMLAttributes,
  type ReactNode,
  useState,
} from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowRight,
  Check,
  ChevronDown,
  Inbox,
  Loader2,
  X,
} from "lucide-react";
import { label, safeExternalUrl } from "@/lib/format";
import { post, type Row } from "@/lib/api";

export function Button({
  children,
  className = "",
  variant = "primary",
  busy,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  busy?: boolean;
}) {
  return (
    <button
      className={`btn btn-${variant} ${className}`}
      {...props}
      disabled={props.disabled || busy}
    >
      {busy && <Loader2 size={16} className="spin" />}
      {children}
    </button>
  );
}
export function LinkButton({
  href,
  children,
  variant = "primary",
}: {
  href: string;
  children: ReactNode;
  variant?: string;
}) {
  return (
    <Link className={`btn btn-${variant}`} href={href}>
      {children}
    </Link>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow || "CREATOR WORKSPACE"}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
export function Card({
  title,
  subtitle,
  action,
  children,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || action) && (
        <header className="card-heading">
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className="card-body">{children}</div>
    </section>
  );
}
export function Notice({
  children,
  tone = "info",
}: {
  children: ReactNode;
  tone?: "info" | "error" | "success" | "warning";
}) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`notice ${tone}`}
    >
      {tone === "success" ? <Check size={18} /> : <AlertCircle size={18} />}
      <div>{children}</div>
    </div>
  );
}
export function Empty({
  title = "还没有内容",
  children,
  action,
}: {
  title?: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Inbox size={28} />
      </div>
      <h3>{title}</h3>
      <p>{children || "添加第一条记录，开始构建你的创作研究库。"}</p>
      {action}
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading">
      <Loader2 size={22} className="spin" /> 正在读取工作区数据…
    </div>
  );
}
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function Status({ value }: { value: unknown }) {
  const s = String(value);
  return (
    <Badge
      tone={
        /SUCCEEDED|APPROVED|COMPLETED|PAID|WON|DELIVERED/.test(s)
          ? "green"
          : /FAILED|REJECTED|CANCELED|LOST/.test(s)
            ? "red"
            : "neutral"
      }
    >
      {label(value)}
    </Badge>
  );
}
export function Demo({ value }: { value?: boolean }) {
  return value ? <Badge tone="amber">DEMO · 演示数据</Badge> : null;
}
export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function Modal({
  title,
  children,
  close,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
}) {
  return (
    <div className="modal-backdrop" onClick={close}>
      <section
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="modal"
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <h2>{title}</h2>
          <button className="icon-button" aria-label="关闭" onClick={close}>
            <X size={20} />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}
export function ExternalLink({
  url,
  children = "查看原始作品",
}: {
  url: unknown;
  children?: ReactNode;
}) {
  const safe = safeExternalUrl(url);
  return safe ? (
    <a
      className="text-link"
      href={safe}
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
      <ArrowRight size={14} />
    </a>
  ) : (
    <span className="muted text-sm">未提供来源链接</span>
  );
}
export function Stat({
  label: caption,
  value,
  detail,
  icon,
}: {
  label: string;
  value: ReactNode;
  detail: string;
  icon?: ReactNode;
}) {
  return (
    <div className="stat">
      <div className="stat-top">
        {caption}
        <span>{icon}</span>
      </div>
      <strong>{value}</strong>
      <p>{detail}</p>
    </div>
  );
}
export type FormField = {
  name: string;
  label: string;
  type?: string;
  required?: boolean;
  placeholder?: string;
  options?: { value: string; label: string }[];
  hint?: string;
  defaultValue?: string | number;
};
export function DataForm({
  fields,
  endpoint,
  onDone,
  onSaved,
  fieldAfter,
  initial = {},
  method = "POST",
  submit = "保存",
  children,
}: {
  fields: FormField[];
  endpoint: string;
  onDone?: () => void;
  onSaved?: (record: Row) => Promise<void>;
  fieldAfter?: Record<string, ReactNode>;
  initial?: Record<string, any>;
  method?: string;
  submit?: string;
  children?: ReactNode;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [success, setSuccess] = useState("");
  return (
    <form
      method="post"
      className="stack"
      onSubmit={async (e) => {
        e.preventDefault();
        const form = e.currentTarget;
        const fd = new FormData(form);
        const data: Record<string, any> = {};
        for (const field of fields) {
          const v = fd.get(field.name);
          data[field.name] =
            field.type === "number" ? (v === "" ? null : Number(v)) : v || null;
        }
        setBusy(true);
        setError("");
        setSuccess("");
        try {
          const record = await post(endpoint, data, method);
          await onSaved?.(record);
          setSuccess("已保存到工作区。");
          onDone?.();
          if (method === "POST") form.reset();
        } catch (err) {
          setError((err as Error).message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <div className="form-grid">
        {fields.map((field) => (
          <Fragment key={field.name}>
            <Field label={field.label} hint={field.hint}>
              {field.options ? (
                <select
                  name={field.name}
                  required={field.required}
                  defaultValue={initial[field.name] ?? field.defaultValue ?? ""}
                >
                  {!field.required && <option value="">请选择</option>}
                  {field.options.map((x) => (
                    <option key={x.value} value={x.value}>
                      {x.label}
                    </option>
                  ))}
                </select>
              ) : field.type === "textarea" ? (
                <textarea
                  name={field.name}
                  required={field.required}
                  defaultValue={initial[field.name] ?? field.defaultValue ?? ""}
                  placeholder={field.placeholder}
                  rows={4}
                />
              ) : (
                <input
                  name={field.name}
                  type={field.type || "text"}
                  min={field.type === "number" ? 0 : undefined}
                  step={field.type === "number" ? "any" : undefined}
                  required={field.required}
                  defaultValue={initial[field.name] ?? field.defaultValue ?? ""}
                  placeholder={field.placeholder}
                />
              )}
            </Field>
            {fieldAfter?.[field.name]}
          </Fragment>
        ))}
      </div>
      {children}
      {error && <Notice tone="error">{error}</Notice>}
      {success && <Notice tone="success">{success}</Notice>}
      <div>
        <Button type="submit" busy={busy}>
          {submit}
          <ArrowRight size={15} />
        </Button>
      </div>
    </form>
  );
}
export function RecordList({
  items,
  render,
  empty,
}: {
  items: Row[];
  render: (row: Row) => ReactNode;
  empty?: string;
}) {
  return items.length ? (
    <div className="record-list">
      {items.map((row) => (
        <div key={row.id} className="record">
          {render(row)}
        </div>
      ))}
    </div>
  ) : (
    <Empty title={empty} />
  );
}
export function JsonDetails({
  data,
  title = "查看记录详情",
}: {
  data: unknown;
  title?: string;
}) {
  return (
    <details className="json-details">
      <summary>
        {title}
        <ChevronDown size={15} />
      </summary>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </details>
  );
}
