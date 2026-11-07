"use client";
import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  ChartNoAxesCombined,
  FileText,
  FlaskConical,
  Plus,
  ScanText,
  Users,
} from "lucide-react";
import { rows, useResource } from "@/lib/api";
import { dateLabel, formatMetric } from "@/lib/format";
import {
  Card,
  Empty,
  LinkButton,
  Loading,
  Notice,
  PageHeading,
  Stat,
  Status,
} from "../ui";
export default function Dashboard() {
  const r = useResource("/dashboard");
  if (r.loading) return <Loading />;
  const d = r.data || {},
    counts = d.counts || {};
  return (
    <>
      <PageHeading
        eyebrow="YOUR CREATIVE COMMAND CENTER"
        title="创作，始于更好的洞察。"
        description="欢迎回来。这里记录你的内容研究、每一次实验，以及正在发生的进步。"
        action={
          <LinkButton href="/analyze">
            <Plus size={17} />
            新建内容分析
          </LinkButton>
        }
      />
      {r.error && <Notice tone="error">{r.error}</Notice>}
      <div className="stats-grid">
        <Stat
          label="研究作品"
          value={formatMetric(counts.contents ?? 0)}
          detail="工作区已提交内容"
          icon={<FileText size={18} />}
        />
        <Stat
          label="分析报告"
          value={formatMetric(counts.analyses ?? 0)}
          detail="保留结论与来源证据"
          icon={<ScanText size={18} />}
        />
        <Stat
          label="创作账号"
          value={formatMetric(counts.accounts ?? rows(d.accounts).length)}
          detail="持续积累账号画像"
          icon={<Users size={18} />}
        />
        <Stat
          label="进行中的实验"
          value={formatMetric(counts.experiments ?? 0)}
          detail="让下一次修改可追踪"
          icon={<FlaskConical size={18} />}
        />
      </div>
      <section className="workspace-banner">
        <div>
          <span className="eyebrow">MAKE YOUR NEXT PIECE BETTER</span>
          <h2>
            把一个创作问题，
            <br />
            变成下一次实验。
          </h2>
          <p>上传作品 → 观察结构 → 寻找依据 → 制定修改计划</p>
          <Link href="/analyze">
            开始研究你的作品
            <ArrowRight size={17} />
          </Link>
        </div>
        <div className="banner-graphic" aria-hidden="true">
          <div>
            <ScanText size={36} />
          </div>
          <span />
          <div>
            <FlaskConical size={36} />
          </div>
        </div>
      </section>
      <div className="dashboard-columns">
        <Card
          title="最近的内容研究"
          subtitle="从真实素材开始，保留你的每一次判断"
          action={
            <Link href="/analyze" className="text-link">
              全部分析
              <ArrowRight size={14} />
            </Link>
          }
        >
          {rows(d.analyses).length ? (
            <div className="record-list">
              {rows(d.analyses)
                .slice(0, 6)
                .map((a) => (
                  <Link
                    key={a.id}
                    href={`/analyses/${a.id}`}
                    className="record analysis-row"
                  >
                    <div className="file-icon">
                      <FileText size={20} />
                    </div>
                    <div className="grow">
                      <h3>{a.title || a.content_title || "内容研究报告"}</h3>
                      <p>
                        {dateLabel(a.created_at)} ·{" "}
                        {a.mode === "ai" ? "MiMo AI" : "本地基础分析"}
                      </p>
                    </div>
                    <Status value={a.status} />
                    <ArrowRight size={16} />
                  </Link>
                ))}
            </div>
          ) : (
            <Empty
              title="你的第一份洞察，正在等待开始"
              action={
                <LinkButton href="/analyze" variant="secondary">
                  上传第一份作品
                  <ArrowRight size={15} />
                </LinkButton>
              }
            >
              一段视频、一组图文，或一份还在打磨的脚本，都可以成为研究的起点。
            </Empty>
          )}
        </Card>
        <Card title="你的研究路径" subtitle="建立一个能够持续迭代的创作系统">
          <div className="path-list">
            {[
              {
                href: "/accounts",
                icon: Users,
                title: "完善账号档案",
                text: "记录定位、受众与内容风格",
              },
              {
                href: "/library",
                icon: BookOpen,
                title: "积累对标作品",
                text: "保存有来源、有价值的参考",
              },
              {
                href: "/analytics",
                icon: ChartNoAxesCombined,
                title: "导入内容表现",
                text: "用可用数据检验创作假设",
              },
              {
                href: "/experiments",
                icon: FlaskConical,
                title: "开启一次实验",
                text: "记录修改、观测窗口与结果",
              },
            ].map((x, i) => (
              <Link href={x.href} key={x.href}>
                <span className="path-number">0{i + 1}</span>
                <div>
                  <h3>{x.title}</h3>
                  <p>{x.text}</p>
                </div>
                <ArrowRight size={16} />
              </Link>
            ))}
          </div>
        </Card>
      </div>
      <Card title="最近订单" subtitle="交付与验收在这里保持同步">
        {rows(d.orders).length ? (
          <div className="record-list">
            {rows(d.orders).map((o) => (
              <Link className="record" key={o.id} href="/orders">
                <div>
                  <h3>{o.title || `订单 ${o.id.slice(0, 8)}`}</h3>
                  <p>{dateLabel(o.created_at)}</p>
                </div>
                <Status value={o.status} />
              </Link>
            ))}
          </div>
        ) : (
          <div className="inline-empty">
            暂无订单。你的研究工作区可独立使用；服务需求可从官网提交。
          </div>
        )}
      </Card>
    </>
  );
}
