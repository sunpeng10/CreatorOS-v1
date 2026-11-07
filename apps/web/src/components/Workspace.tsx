"use client";
import Link from "next/link";
import { Suspense } from "react";
import Shell from "./Shell";
import { Loading } from "./ui";
import Dashboard from "./pages/Dashboard";
import { Analyze, AnalysisReport } from "./pages/Analysis";
import { Library, Recommendations } from "./pages/Library";
import { Accounts, Analytics, Experiments } from "./pages/Research";
import {
  AdminOverview,
  Approvals,
  Leads,
  Orders,
  Services,
} from "./pages/Operations";
import {
  Agents,
  DataManagement,
  Finance,
  Settings,
  Tickets,
} from "./pages/Management";
export default function Workspace({ path }: { path: string }) {
  let page;
  switch (path) {
    case "dashboard":
      page = <Dashboard />;
      break;
    case "analyze":
    case "analyses":
      page = <Analyze />;
      break;
    case "library":
      page = <Library />;
      break;
    case "recommendations":
      page = <Recommendations />;
      break;
    case "accounts":
      page = <Accounts />;
      break;
    case "analytics":
      page = <Analytics />;
      break;
    case "experiments":
      page = <Experiments />;
      break;
    case "settings":
      page = <Settings />;
      break;
    case "orders":
      page = <Orders />;
      break;
    case "tickets":
      page = <Tickets />;
      break;
    case "admin":
      page = <AdminOverview />;
      break;
    case "admin/leads":
      page = <Leads />;
      break;
    case "admin/services":
      page = <Services />;
      break;
    case "admin/orders":
      page = <Orders admin />;
      break;
    case "admin/approvals":
      page = <Approvals />;
      break;
    case "admin/tickets":
      page = <Tickets admin />;
      break;
    case "admin/finance":
      page = <Finance />;
      break;
    case "admin/agents":
      page = <Agents />;
      break;
    case "admin/data":
      page = <DataManagement />;
      break;
    default:
      page = path.startsWith("analyses/") ? (
        <AnalysisReport id={path.split("/")[1]} />
      ) : (
        <div className="empty">
          <h1>找不到这个页面</h1>
          <Link href="/dashboard" className="btn btn-primary">
            返回工作台
          </Link>
        </div>
      );
  }
  return (
    <Shell admin={path.startsWith("admin")}>
      <Suspense fallback={<Loading />}>{page}</Suspense>
    </Shell>
  );
}
