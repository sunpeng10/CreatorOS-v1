"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import {
  Activity,
  ArrowUpRight,
  BookOpen,
  Bot,
  ChartNoAxesCombined,
  ChevronRight,
  ClipboardList,
  Database,
  FlaskConical,
  LayoutDashboard,
  LifeBuoy,
  LogOut,
  Menu,
  Search,
  Settings,
  ShieldCheck,
  ShoppingBag,
  SlidersHorizontal,
  Sparkles,
  Upload,
  Users,
  Wallet,
  X,
} from "lucide-react";
import { api, ApiError, post, type Row } from "@/lib/api";
import { Loading, Notice } from "./ui";
const clientLinks = [
  { href: "dashboard", label: "工作台总览", icon: LayoutDashboard },
  { href: "analyze", label: "内容分析", icon: ScanIcon },
  { href: "library", label: "对标作品库", icon: BookOpen },
  { href: "recommendations", label: "发现与推荐", icon: Search },
  { href: "analytics", label: "数据洞察", icon: ChartNoAxesCombined },
  { href: "experiments", label: "创作实验", icon: FlaskConical },
  { href: "accounts", label: "账号档案", icon: Users },
  { href: "orders", label: "我的订单", icon: ShoppingBag },
  { href: "tickets", label: "服务与反馈", icon: LifeBuoy },
];
const adminLinks = [
  { href: "admin", label: "公司总览", icon: LayoutDashboard },
  { href: "admin/leads", label: "客户与线索", icon: Users },
  { href: "admin/services", label: "服务与报价", icon: SlidersHorizontal },
  { href: "admin/orders", label: "订单与交付", icon: ShoppingBag },
  { href: "admin/approvals", label: "人工审批", icon: ShieldCheck },
  { href: "admin/tickets", label: "客服工单", icon: LifeBuoy },
  { href: "admin/finance", label: "经营报表", icon: Wallet },
  { href: "admin/agents", label: "Agent 控制台", icon: Bot },
  { href: "admin/data", label: "数据与审计", icon: Database },
];
function ScanIcon({ size = 19 }: { size?: number }) {
  return <Activity size={size} />;
}
export default function Shell({
  children,
}: {
  children: ReactNode;
}) {
  const path = usePathname(),
    router = useRouter();
  const admin = path === "/admin" || path.startsWith("/admin/");
  const [user, setUser] = useState<Row | null>(null),
    [error, setError] = useState(""),
    [open, setOpen] = useState(false);
  useEffect(() => {
    api("/auth/me")
      .then((d) => setUser(d.user || d))
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) router.replace("/login");
        else setError(e.message);
      });
  }, [router]);
  const links = admin ? adminLinks : clientLinks;
  const current =
    links.find((l) => path === `/${l.href}`)?.label ||
    (path.startsWith("/analyses/") ? "分析报告" : "工作区设置");
  if (error)
    return (
      <div className="standalone-error">
        <Notice tone="error">{error}</Notice>
        <Link href="/login" className="btn btn-primary">
          返回登录
        </Link>
      </div>
    );
  if (!user) return <Loading />;
  if (admin && user.role !== "OWNER_ADMIN")
    return (
      <div className="standalone-error">
        <ShieldCheck size={36} />
        <h1>此页面仅限工作区管理员</h1>
        <p>你的创作者工作区可继续正常使用。</p>
        <Link href="/dashboard" className="btn btn-primary">
          返回工作台
        </Link>
      </div>
    );
  return (
    <div className="app-shell">
      {open && (
        <div className="mobile-overlay" onClick={() => setOpen(false)} />
      )}
      <aside className={`sidebar ${open ? "is-open" : ""}`}>
        <Link className="brand" href="/">
          <span className="brand-symbol">
            <FlaskConical size={21} />
          </span>
          Creator<span className="brand-os">OS</span>
          <button
            aria-label="关闭导航"
            className="mobile-only icon-button"
            onClick={(e) => {
              e.preventDefault();
              setOpen(false);
            }}
          >
            <X size={18} />
          </button>
        </Link>
        <div className="workspace-switch">
          <div className="workspace-avatar">
            {admin ? <ShieldCheck size={18} /> : <FlaskConical size={18} />}
          </div>
          <div>
            <b>{admin ? "公司运营中心" : "我的创作实验室"}</b>
            <span>{admin ? "OWNER WORKSPACE" : "PERSONAL WORKSPACE"}</span>
          </div>
          <ChevronRight size={14} />
        </div>
        <div className="nav-caption">{admin ? "公司运营" : "研究与创作"}</div>
        <nav className="side-nav">
          {links.map((l) => (
            <Link
              key={l.href}
              href={`/${l.href}`}
              onClick={() => setOpen(false)}
              className={
                path === `/${l.href}` ||
                (l.href === "analyze" && path.startsWith("/analyses"))
                  ? "active"
                  : ""
              }
            >
              <l.icon size={19} />
              {l.label}
              {path === `/${l.href}` && <span className="active-dot" />}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <Sparkles size={18} />
            <strong>下一次创作，从证据出发</strong>
            <p>
              保留观察，验证假设。
              <br />
              让你的研究持续积累。
            </p>
            <Link href="/analyze">
              开始内容分析
              <ArrowUpRight size={14} />
            </Link>
          </div>
          {user.role === "OWNER_ADMIN" && (
            <Link
              className="side-bottom-link"
              href={admin ? "/dashboard" : "/admin"}
            >
              {admin ? (
                <LayoutDashboard size={17} />
              ) : (
                <ShieldCheck size={17} />
              )}
              切换到{admin ? "创作工作台" : "老板后台"}
            </Link>
          )}
          <Link className="side-bottom-link" href="/settings">
            <Settings size={17} />
            工作区设置
          </Link>
          <button
            className="side-bottom-link"
            onClick={async () => {
              try {
                await post("/auth/logout");
                router.push("/login");
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            <LogOut size={17} />
            退出登录
          </button>
          <div className="user-card">
            <div className="user-avatar">
              {String(user.name || user.email)
                .slice(0, 1)
                .toUpperCase()}
            </div>
            <div>
              <b>{user.name || "创作者"}</b>
              <small>{user.email}</small>
            </div>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs">
            <button
              className="mobile-only icon-button"
              aria-label="打开导航"
              onClick={() => setOpen(true)}
            >
              <Menu size={21} />
            </button>
            <span>{admin ? "公司运营" : "创作工作区"}</span>
            <ChevronRight size={14} />
            <strong>{current}</strong>
          </div>
          <div className="topbar-right">
            <span className="local-badge">
              <span />
              本地私有工作区
            </span>
            <Link href="/analyze" className="topbar-upload">
              <Upload size={15} />
              新建分析
            </Link>
          </div>
        </header>
        <main className="workspace-main">{children}</main>
        <footer className="workspace-footer">
          <span>CreatorOS · 爆款实验室</span>
          <span>
            <ClipboardList size={13} />
            基于证据 · 保留不确定性
          </span>
        </footer>
      </div>
    </div>
  );
}
