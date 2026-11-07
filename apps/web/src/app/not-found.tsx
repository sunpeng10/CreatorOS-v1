import Link from "next/link";
export default function NotFound() {
  return (
    <main className="auth-layout">
      <section className="auth-form">
        <h1>找不到这个页面</h1>
        <p>链接可能已失效，或你尚未登录对应工作区。</p>
        <Link className="btn btn-primary" href="/dashboard">
          返回工作台
        </Link>
      </section>
    </main>
  );
}
