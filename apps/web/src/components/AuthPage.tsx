"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  ChartNoAxesCombined,
  Check,
  FlaskConical,
} from "lucide-react";
import { api, post, type Row } from "@/lib/api";
import { Button, Field, Notice } from "./ui";
import styles from "./AuthArtwork.module.css";
export default function AuthPage({ register = false }: { register?: boolean }) {
  const router = useRouter();
  const [hydrated, setHydrated] = useState(false);
  const [returnTo, setReturnTo] = useState("/dashboard");
  useEffect(() => {
    const next = new URLSearchParams(window.location.search).get("next") || "";
    const target =
      next === "/#contact" || /^\/orders(?:\?|$)/.test(next)
        ? next
        : "/dashboard";
    setReturnTo(target);
    let active = true;
    api<Row>("/auth/me")
      .then((user) => {
        if (active)
          router.replace(
            target === "/dashboard" && user.role === "OWNER_ADMIN"
              ? "/admin"
              : target,
          );
      })
      .catch(() => {
        if (active) setHydrated(true);
      });
    return () => {
      active = false;
    };
  }, [router]);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <main className="auth-layout">
      <section className="auth-story">
        <Link className="brand" href="/">
          <span className="brand-symbol">
            <FlaskConical size={22} />
          </span>
          Creator<span className="brand-os">OS</span>
        </Link>
        <div>
          <span className="eyebrow">YOUR NEXT CREATIVE ADVANTAGE</span>
          <h1>
            好内容，
            <br />
            从一个好问题开始。
          </h1>
          <p>
            把灵感变成可验证的创作决策。
            <br />
            研究、实验、复盘，让每一次进步都有迹可循。
          </p>
          <div className={`auth-motif ${styles.motif}`}>
            <ChartNoAxesCombined size={100} strokeWidth={1} />
            <span>INSIGHT → EXPERIMENT → GROWTH</span>
          </div>
        </div>
        <small>CreatorOS · 爆款实验室 / JUNCTION 2026</small>
      </section>
      <section className="auth-form">
        <Link href="/" className="back-link">
          ← 返回官网
        </Link>
        <div className="auth-form-inner">
          <BadgeText />
          <h1>{register ? "建立你的创作工作区" : "欢迎回到实验室"}</h1>
          <p>
            {register
              ? "用真实资料积累洞察，从你的第一份内容分析开始。"
              : "登录，继续你的下一次创作实验。"}
          </p>
          <form
            method="post"
            className="stack"
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              const f = new FormData(e.currentTarget);
              try {
                const user = await post<Row>(
                  `/auth/${register ? "register" : "login"}`,
                  {
                    email: f.get("email"),
                    password: f.get("password"),
                    remember_me: f.get("remember_me") === "on",
                    ...(register ? { name: f.get("name") } : {}),
                  },
                );
                router.push(
                  returnTo === "/dashboard" && user.role === "OWNER_ADMIN"
                    ? "/admin"
                    : returnTo,
                );
                router.refresh();
              } catch (err) {
                setError((err as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            {register && (
              <Field label="你的称呼">
                <input
                  name="name"
                  autoComplete="name"
                  required
                  maxLength={80}
                  placeholder="怎样称呼你"
                />
              </Field>
            )}
            <Field label="邮箱地址">
              <input
                name="email"
                type="email"
                autoComplete="email"
                required
                placeholder="you@example.com"
              />
            </Field>
            <Field
              label="密码"
              hint={
                register
                  ? "至少 10 个字符，建议混合字母、数字和符号。"
                  : undefined
              }
            >
              <input
                name="password"
                type="password"
                autoComplete={register ? "new-password" : "current-password"}
                minLength={register ? 10 : undefined}
                required
                placeholder="输入密码"
              />
            </Field>
            <label className="check">
              <input type="checkbox" name="remember_me" defaultChecked />
              <span>记住登录（30天）</span>
            </label>
            {register && (
              <label className="check">
                <input type="checkbox" required />
                <span>
                  我已阅读并同意{" "}
                  <Link href="/#privacy">隐私说明与用户协议草稿</Link>
                </span>
              </label>
            )}
            {error && <Notice tone="error">{error}</Notice>}
            <Button busy={busy} disabled={!hydrated} type="submit">
              {!hydrated
                ? "正在检查登录状态…"
                : register
                  ? "创建工作区"
                  : "登录工作区"}
              <ArrowRight size={17} />
            </Button>
          </form>
          <p className="auth-switch">
            {register ? "已有账号？" : "第一次来到这里？"}{" "}
            <Link
              href={`${register ? "/login" : "/register"}?next=${encodeURIComponent(returnTo)}`}
            >
              {register ? "立即登录" : "免费创建工作区"}
            </Link>
          </p>
          <div className="auth-trust">
            <Check size={15} /> 私有工作区 <span>·</span> 按需启用 AI{" "}
            <span>·</span> 数据可导出
          </div>
        </div>
      </section>
    </main>
  );
}
function BadgeText() {
  return <div className="eyebrow">CREATOROS / 爆款实验室</div>;
}
