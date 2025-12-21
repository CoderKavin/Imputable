import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { AppLayout } from "@/components/app";
import { DashboardContent } from "./dashboard-content";

/**
 * Dashboard Page
 *
 * Main landing page after sign-in.
 * Shows overview stats and quick actions.
 * Requires authentication (handled by middleware).
 */
export default async function DashboardPage() {
  const { userId, orgId } = await auth();

  // This should be handled by middleware, but double-check
  if (!userId) {
    redirect("/sign-in");
  }

  return (
    <AppLayout
      title="Dashboard"
      subtitle="Welcome back! Here's what's happening."
    >
      <DashboardContent hasOrg={!!orgId} />
    </AppLayout>
  );
}
