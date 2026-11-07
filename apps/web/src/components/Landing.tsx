"use client";
import Link from "next/link";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  ChartNoAxesCombined,
  Check,
  FlaskConical,
  Focus,
  Layers3,
  LockKeyhole,
  Play,
  ScanText,
  Sparkles,
} from "lucide-react";
import { rows, useResource } from "@/lib/api";
import { money } from "@/lib/format";
import { DataForm, Notice } from "./ui";
export default function Landing() {
  const services = useResource("/services"),
    me = useResource("/auth/me");
  return (
    <div className="landing">
      <header className="site-nav">
        <Link href="/" className="brand">
          <span className="brand-symbol">
            <FlaskConical size={21} />
          </span>
          Creator<span className="brand-os">OS</span>
          <span className="brand-cn">爆款实验室</span>
        </Link>
        <nav>
          <a href="#method">产品方法</a>
          <a href="#features">功能探索</a>
          <a href="#pricing">服务方案</a>
        </nav>
        <div className="nav-actions">
          <Link href="/login">登录</Link>
          <Link href="/register" className="btn btn-dark">
            进入工作台
            <ArrowUpRight size={16} />
          </Link>
        </div>
      </header>
      <main>
        <section className="hero">
          <div className="hero-copy">
            <div className="hero-kicker">
              <span /> 为认真创作的人，建立增长方法
            </div>
            <h1>
              让每一次创作
              <br />
              都有
              <span>
                数据依据
                <svg viewBox="0 0 400 20" aria-hidden="true">
                  <path d="M4 14 Q190 -2 396 10" />
                </svg>
              </span>
              。
            </h1>
            <p>
              从「感觉不错」到「知道为什么」。
              <br />用 AI 拆解内容，用真实案例寻找方向，
              <br />
              把下一次创作，变成一次有依据的实验。
            </p>
            <div className="hero-actions">
              <Link className="btn btn-primary" href="/register">
                开始你的第一个实验
                <ArrowRight size={18} />
              </Link>
              <a className="btn btn-text" href="#method">
                <Play size={16} />
                了解工作方式
              </a>
            </div>
            <div className="hero-footnote">
              <Check size={14} /> 本地基础分析可用 <span>·</span> AI 按需启用{" "}
              <span>·</span> 无需连接社交账号
            </div>
          </div>
          <div className="hero-visual">
            <div className="orbit-label">CONTENT INTELLIGENCE / 01</div>
            <div className="visual-dots" />
            <div className="specimen">
              <header>
                <span className="mini-logo">
                  <ScanText size={16} />
                </span>
                <span>内容研究报告</span>
                <span className="tiny-chip">流程示意</span>
              </header>
              <div className="specimen-body">
                <div className="specimen-icon">
                  <Focus size={32} strokeWidth={1.3} />
                </div>
                <h3>
                  好内容的下一步
                  <br />
                  是可验证的洞察。
                </h3>
                <div className="specimen-line">
                  <span>01</span>
                  <div>
                    <b>观察内容结构</b>
                    <small>主题 · 开头钩子 · 叙事节奏</small>
                  </div>
                  <Check size={16} />
                </div>
                <div className="specimen-line">
                  <span>02</span>
                  <div>
                    <b>连接数据与证据</b>
                    <small>来源 · 可用指标 · 结论局限</small>
                  </div>
                  <Check size={16} />
                </div>
                <div className="specimen-line">
                  <span>03</span>
                  <div>
                    <b>设计下一次实验</b>
                    <small>标题 · 脚本 · 待验证假设</small>
                  </div>
                  <ArrowRight size={16} />
                </div>
              </div>
              <footer>
                <span className="status-dot" />
                你的创作，由证据驱动
              </footer>
            </div>
            <div className="floating-note">
              <Sparkles size={18} />
              <div>
                <strong>灵感有方向，迭代有记录</strong>
                <span>从一份作品开始建立研究资产</span>
              </div>
            </div>
            <div className="visual-caption">
              RESEARCH. CREATE. LEARN. REPEAT.
            </div>
          </div>
        </section>
        <section className="audience-strip">
          <span>为知识型创作者设计</span>
          <b>AI 工具探索</b>
          <b>编程与教育</b>
          <b>知识科普</b>
          <b>内容研究团队</b>
          <ArrowDown size={18} />
        </section>
        <section id="method" className="landing-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">A BETTER CREATIVE LOOP</span>
              <h2>
                少一点猜测，
                <br />
                多一点可积累的方法。
              </h2>
            </div>
            <p>
              研究不是创作的终点。
              <br />
              让每一份洞察，都能走向下一次行动。
            </p>
          </div>
          <div className="method-grid">
            {[
              {
                n: "01",
                icon: ScanText,
                title: "提交你的作品",
                text: "视频、图集、字幕或文稿，保留真实素材与创作背景。",
              },
              {
                n: "02",
                icon: Layers3,
                title: "拆解，找到依据",
                text: "将直接观察、数据支持与推测分开，让结论能够被追溯。",
              },
              {
                n: "03",
                icon: FlaskConical,
                title: "带着假设再创作",
                text: "编辑标题与脚本，记录修改计划，用后续数据回看结果。",
              },
            ].map((x) => (
              <article key={x.n}>
                <div className="method-top">
                  <x.icon size={26} strokeWidth={1.5} />
                  <span>{x.n}</span>
                </div>
                <h3>{x.title}</h3>
                <p>{x.text}</p>
              </article>
            ))}
          </div>
        </section>
        <section id="features" className="feature-section">
          <div>
            <span className="eyebrow">
              ONE WORKSPACE. YOUR CREATIVE SYSTEM.
            </span>
            <h2>
              把零散的灵感，
              <br />
              变成你的研究资产。
            </h2>
            <p>
              在同一个工作区里，管理内容、寻找参考、
              <br />
              观察表现、追踪实验。每一个决策都有来处。
            </p>
            <Link href="/register" className="text-link">
              探索完整工作台
              <ArrowRight size={16} />
            </Link>
          </div>
          <div className="feature-grid">
            {[
              {
                icon: ScanText,
                title: "内容诊断",
                text: "本地解析 + 按需 MiMo 分析",
              },
              {
                icon: BookOpen,
                title: "对标作品库",
                text: "本人授权资料，来源清晰可查",
              },
              {
                icon: ChartNoAxesCombined,
                title: "数据洞察",
                text: "导入真实指标，诚实呈现缺失",
              },
              {
                icon: FlaskConical,
                title: "创作实验",
                text: "记录假设、版本与观测窗口",
              },
            ].map((x) => (
              <article key={x.title}>
                <x.icon size={23} />
                <h3>{x.title}</h3>
                <p>{x.text}</p>
              </article>
            ))}
          </div>
        </section>
        <section id="pricing" className="landing-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">START SMALL. LEARN CONTINUOUSLY.</span>
              <h2>从适合你的研究深度开始。</h2>
            </div>
            <p>
              试运营服务报价，具体交付范围以人工确认报价为准。
              <br />
              AI 模型使用费用单独显示，不代表实际支付。
            </p>
          </div>
          <div className="pricing-grid">
            {rows(services.data).length ? (
              rows(services.data).map((s, i) => (
                <article key={s.id} className={i === 1 ? "featured-price" : ""}>
                  <span className="eyebrow">
                    {i === 1 ? "深入研究" : "创作者服务"}
                  </span>
                  <h3>{s.name}</h3>
                  <strong>
                    {money(s.price)}
                    <small> / 试运营报价</small>
                  </strong>
                  <p>
                    {s.description ||
                      "具体分析范围与交付内容由工作区管理员确认。"}
                  </p>
                  <Link
                    className={`btn ${i === 1 ? "btn-primary" : "btn-secondary"}`}
                    href={
                      me.data
                        ? `/orders?service_id=${s.id}`
                        : `/login?next=${encodeURIComponent(`/orders?service_id=${s.id}`)}`
                    }
                  >
                    选择此服务
                    <ArrowRight size={16} />
                  </Link>
                </article>
              ))
            ) : (
              <article className="pricing-empty">
                <h3>让研究从真实需求开始</h3>
                <p>
                  服务方案正在试运营。留下你的创作方向，我们将根据需求建立可审核的报价。
                </p>
                <a className="btn btn-primary" href="#contact">
                  提交需求
                  <ArrowRight size={16} />
                </a>
              </article>
            )}
          </div>
          {services.error && (
            <Notice>服务报价暂时无法读取；你仍可进入工作区或稍后再试。</Notice>
          )}
        </section>
        <section id="contact" className="contact-section">
          <div>
            <span className="eyebrow">LET’S FIND YOUR NEXT QUESTION</span>
            <h2>
              下一条内容，
              <br />
              你想验证什么？
            </h2>
            <p>
              告诉我们你的创作方向和当前问题。
              <br />
              提交后会生成真实的咨询记录。
              <br />
              使用客户账号提交后，需求状态与回复会同步到“服务与反馈”。
            </p>
            <span className="privacy-note">
              <LockKeyhole size={16} /> 仅用于回应本次咨询，不公开你的联系方式。
            </span>
          </div>
          {me.data?.role === "CLIENT_USER" ? (
            <DataForm
              endpoint="/leads"
              initial={{ contact: me.data.email }}
              fields={[
                {
                  name: "contact",
                  label: "联系方式",
                  required: true,
                  placeholder: "邮箱 / 微信 / 手机",
                },
                {
                  name: "need",
                  label: "你希望解决的问题",
                  type: "textarea",
                  required: true,
                  placeholder: "例如：如何把编程教程的开头讲得更清楚？",
                },
                {
                  name: "campaign",
                  label: "如何了解到我们",
                  defaultValue: "官网",
                  placeholder: "活动 / 朋友推荐 / 其他",
                },
              ]}
              submit="发送咨询"
            />
          ) : (
            <Notice>
              请先登录客户账号，再提交需求或选择服务。
              <br />
              <Link className="text-link" href="/login?next=%2F%23contact">
                登录后提交需求
              </Link>
              <Link className="text-link" href="/register?next=%2F%23contact">
                注册客户账号
              </Link>
            </Notice>
          )}
        </section>
        <section className="faq-section">
          <h2>开始前，你可能想知道</h2>
          {[
            {
              q: "没有 AI 配置，能使用吗？",
              a: "可以。素材管理、本地基础分析、作品库、数据导入和实验记录均可使用。MiMo 分析需要有效配置，并由你明确同意费用预算后发起。",
            },
            {
              q: "平台会自动抓取作品或发布内容吗？",
              a: "本版使用你主动上传或授权导入的资料，不绕过平台限制，不自动发布内容。作品链接只作为来源参考。",
            },
            {
              q: "分析能保证内容变成爆款吗？",
              a: "不能。我们呈现可观察事实、证据与不确定性，帮助你提出更好的假设。单次表现改善不能证明因果，更不代表增长承诺。",
            },
          ].map((x) => (
            <details key={x.q}>
              <summary>
                {x.q}
                <span>+</span>
              </summary>
              <p>{x.a}</p>
            </details>
          ))}
        </section>
        <section id="privacy" className="legal-section">
          <h3>隐私说明与用户协议 · 本地试运营草稿</h3>
          <p>
            仅上传你有权使用的内容。作品、指标、账号和报告保存在本地工作区，并通过组织权限隔离。启用
            MiMo AI
            时，你授权将分析所需内容发送给已配置的模型服务；开始前会单独确认预算。可在设置中导出数据或提交删除申请。分析仅作创作参考，真实支付、对外发布和高风险操作需人工审批。公开运营前需要完成正式协议、隐私与支付服务配置。
          </p>
        </section>
      </main>
      <footer className="site-footer">
        <Link href="/" className="brand">
          <FlaskConical size={22} />
          CreatorOS
        </Link>
        <span>让每一次创作都有数据依据。</span>
        <small>独立创作 · 持续实验 / JUNCTION 2026</small>
      </footer>
    </div>
  );
}
