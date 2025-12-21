import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { AppLayout } from "@/components/app";
import { SettingsContent } from "./settings-content";

/**
 * Settings Page
 *
 * Organization settings including integrations, billing, and team management.
 */
export default async function SettingsPage() {
  const { userId, orgId } = await auth();

  if (!userId) {
    redirect("/sign-in");
  }

  return (
    <AppLayout
      title="Settings"
      subtitle="Manage your organization settings and integrations"
    >
      <SettingsContent hasOrg={!!orgId} />
    </AppLayout>
  );
}
