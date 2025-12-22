"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useOrganization } from "@/contexts/OrganizationContext";
import {
  Building2,
  Loader2,
  Save,
  Trash2,
  AlertCircle,
  Check,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

interface OrgDetails {
  id: string;
  name: string;
  slug: string;
  created_at: string;
  subscription_tier: string;
  member_count: number;
  decision_count: number;
  user_role: string;
}

export function GeneralTab() {
  const { getToken } = useAuth();
  const { currentOrganization, refreshOrganizations } = useOrganization();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [orgDetails, setOrgDetails] = useState<OrgDetails | null>(null);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (currentOrganization?.id) {
      fetchOrgDetails();
    }
  }, [currentOrganization?.id]);

  useEffect(() => {
    if (error || success) {
      const timer = setTimeout(() => {
        setError(null);
        setSuccess(null);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [error, success]);

  async function fetchOrgDetails() {
    if (!currentOrganization?.id) return;

    try {
      setLoading(true);
      const token = await getToken();

      const response = await fetch(`${API_BASE_URL}/me/organization`, {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Organization-ID": currentOrganization.id,
        },
      });

      if (!response.ok) {
        throw new Error("Failed to fetch organization details");
      }

      const data = await response.json();
      setOrgDetails(data);
      setName(data.name);
      setSlug(data.slug);
    } catch (err) {
      console.error("Error fetching org details:", err);
      setError("Failed to load organization details");
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    if (!currentOrganization?.id) return;
    if (!name.trim()) {
      setError("Organization name is required");
      return;
    }
    if (!slug.trim() || slug.length < 3) {
      setError("Slug must be at least 3 characters");
      return;
    }

    try {
      setSaving(true);
      setError(null);
      const token = await getToken();

      const response = await fetch(`${API_BASE_URL}/me/organization`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          "X-Organization-ID": currentOrganization.id,
        },
        body: JSON.stringify({ name: name.trim(), slug: slug.trim().toLowerCase() }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || "Failed to update organization");
      }

      setSuccess("Organization updated successfully");
      await refreshOrganizations();
    } catch (err) {
      console.error("Error updating org:", err);
      setError(err instanceof Error ? err.message : "Failed to update organization");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!currentOrganization?.id) return;
    if (deleteConfirmText !== currentOrganization.name) {
      setError("Please type the organization name to confirm deletion");
      return;
    }

    try {
      setDeleting(true);
      setError(null);
      const token = await getToken();

      const response = await fetch(`${API_BASE_URL}/me/organization`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Organization-ID": currentOrganization.id,
        },
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || "Failed to delete organization");
      }

      await refreshOrganizations();
      window.location.href = "/dashboard";
    } catch (err) {
      console.error("Error deleting org:", err);
      setError(err instanceof Error ? err.message : "Failed to delete organization");
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-zinc-400" />
      </div>
    );
  }

  const isOwner = orgDetails?.user_role === "owner";
  const isAdmin = orgDetails?.user_role === "admin" || isOwner;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
          General Settings
        </h2>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Manage your organization&apos;s basic information and preferences.
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950/50 dark:text-red-400">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}
      {success && (
        <div className="flex items-center gap-2 rounded-xl bg-green-50 px-4 py-3 text-sm text-green-700 dark:bg-green-950/50 dark:text-green-400">
          <Check className="h-4 w-4 flex-shrink-0" />
          {success}
        </div>
      )}

      {/* Organization Info */}
      <Card className="rounded-2xl border-zinc-200 dark:border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg">Organization Information</CardTitle>
          <CardDescription>Basic details about your organization</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Organization Name
              </label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="My Organization"
                disabled={!isAdmin}
                className="rounded-xl"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                URL Slug
              </label>
              <Input
                value={slug}
                onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"))}
                placeholder="my-organization"
                disabled={!isAdmin}
                className="rounded-xl"
              />
              <p className="text-xs text-zinc-500">
                Used in URLs: imputable.app/{slug}
              </p>
            </div>
          </div>

          {isAdmin && (
            <div className="flex justify-end pt-2">
              <Button
                onClick={handleSave}
                disabled={saving}
                className="rounded-xl"
              >
                {saving ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-2 h-4 w-4" />
                )}
                Save Changes
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Organization Stats */}
      <Card className="rounded-2xl border-zinc-200 dark:border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg">Organization Overview</CardTitle>
          <CardDescription>Statistics and information</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-xl bg-zinc-50 dark:bg-zinc-800/50 p-4">
              <p className="text-sm text-zinc-500 dark:text-zinc-400">Members</p>
              <p className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
                {orgDetails?.member_count || 0}
              </p>
            </div>
            <div className="rounded-xl bg-zinc-50 dark:bg-zinc-800/50 p-4">
              <p className="text-sm text-zinc-500 dark:text-zinc-400">Decisions</p>
              <p className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
                {orgDetails?.decision_count || 0}
              </p>
            </div>
            <div className="rounded-xl bg-zinc-50 dark:bg-zinc-800/50 p-4">
              <p className="text-sm text-zinc-500 dark:text-zinc-400">Plan</p>
              <p className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100 capitalize">
                {orgDetails?.subscription_tier || "Free"}
              </p>
            </div>
          </div>
          {orgDetails?.created_at && (
            <p className="mt-4 text-sm text-zinc-500 dark:text-zinc-400">
              Created on {new Date(orgDetails.created_at).toLocaleDateString()}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Danger Zone */}
      {isOwner && (
        <Card className="rounded-2xl border-red-200 dark:border-red-900/50">
          <CardHeader>
            <CardTitle className="text-lg text-red-600 dark:text-red-400">Danger Zone</CardTitle>
            <CardDescription>Irreversible actions</CardDescription>
          </CardHeader>
          <CardContent>
            {!showDeleteConfirm ? (
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-zinc-900 dark:text-zinc-100">Delete Organization</p>
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">
                    Permanently delete this organization and all its data
                  </p>
                </div>
                <Button
                  variant="destructive"
                  onClick={() => setShowDeleteConfirm(true)}
                  className="rounded-xl"
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="rounded-xl bg-red-50 dark:bg-red-950/30 p-4">
                  <p className="text-sm text-red-700 dark:text-red-400">
                    This action cannot be undone. This will permanently delete the organization
                    <strong> {currentOrganization?.name}</strong>, all decisions, and remove all members.
                  </p>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    Type <strong>{currentOrganization?.name}</strong> to confirm
                  </label>
                  <Input
                    value={deleteConfirmText}
                    onChange={(e) => setDeleteConfirmText(e.target.value)}
                    placeholder="Organization name"
                    className="rounded-xl"
                  />
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setShowDeleteConfirm(false);
                      setDeleteConfirmText("");
                    }}
                    className="rounded-xl"
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="destructive"
                    onClick={handleDelete}
                    disabled={deleting || deleteConfirmText !== currentOrganization?.name}
                    className="rounded-xl"
                  >
                    {deleting ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="mr-2 h-4 w-4" />
                    )}
                    Delete Organization
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default GeneralTab;
