import Workspace from "@/components/Workspace";
export default async function Page({
  params,
}: {
  params: Promise<{ slug: string[] }>;
}) {
  const { slug } = await params;
  return <Workspace path={slug.join("/")} />;
}
