"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useOrganization } from "@/contexts/OrganizationContext";
import {
  Users,
  Loader2,
  UserPlus,
  MoreVertical,
  Mail,
  Shield,
  Trash2,
  AlertCircle,
  Check,
  Crown,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

interface Member {
  id: string;
  user_id: string;
  email: string;
  name: string;
  role: string;
  joined_at: string;
  avatar_url?: string;
}

interface Invite {
  id: string;
  email: string;
  role: string;
  created_at: string;
  expires_at: string;
}

export function TeamTab() {
  const { getToken, user } = useAuth();
  const { currentOrganization } = useOrganization();

  const [loading, setLoading] = useState(true);
  const [members, setMembers] = useState<Member[]>([]);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [currentUserRole, setCurrentUserRole] = useState<string>("member");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Invite modal
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [inviting, setInviting] = useState(false);

  // Role change
  const [changingRole, setChangingRole] = useState<string | null>(null);

  // Remove member
  const [removingMember, setRemovingMember] = useState<string | null>(null);

  useEffect(() => {
    if (currentOrganization?.id) {
      fetchTeamData();
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

  async function fetchTeamData() {
    if (!currentOrganization?.id) return;

    try {
      setLoading(true);
      const token = await getToken();

      const response = await fetch(`${API_BASE_URL}/me/members`, {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Organization-ID": currentOrganization.id,
        },
      });

      if (!response.ok) {
        throw new Error("Failed to fetch team data");
      }

      const data = await response.json();
      setMembers(data.members || []);
      setInvites(data.invites || []);
      setCurrentUserRole(data.current_user_role || "member");
    } catch (err) {
      console.error("Error fetching team:", err);
      setError("Failed to load team members");
    } finally {
      setLoading(false);
    }
  }

  async function handleInvite() {
    if (!currentOrganization?.id) return;
    if (!inviteEmail.trim() || !inviteEmail.includes("@")) {
      setError("Please enter a valid email address");
      return;
    }

    try {
      setInviting(true);
      setError(null);
      const token = await getToken();

      const response = await fetch(`${API_BASE_URL}/me/members`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          "X-Organization-ID": currentOrganization.id,
        },
        body: JSON.stringify({ email: inviteEmail.trim(), role: inviteRole }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || "Failed to send invite");
      }

      const data = await response.json();
      setSuccess(data.message || `Added ${inviteEmail} to the organization`);
      setShowInviteModal(false);
      setInviteEmail("");
      setInviteRole("member");
      await fetchTeamData();
    } catch (err) {
      console.error("Error inviting:", err);
      setError(err instanceof Error ? err.message : "Failed to send invite");
    } finally {
      setInviting(false);
    }
  }

  async function handleChangeRole(memberId: string, newRole: string) {
    if (!currentOrganization?.id) return;

    try {
      setChangingRole(memberId);
      setError(null);
      const token = await getToken();

      const response = await fetch(
        `${API_BASE_URL}/me/members?id=${memberId}`,
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
            "X-Organization-ID": currentOrganization.id,
          },
          body: JSON.stringify({ role: newRole }),
        },
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || "Failed to change role");
      }

      setSuccess("Role updated successfully");
      await fetchTeamData();
    } catch (err) {
      console.error("Error changing role:", err);
      setError(err instanceof Error ? err.message : "Failed to change role");
    } finally {
      setChangingRole(null);
    }
  }

  async function handleRemoveMember(memberId: string) {
    if (!currentOrganization?.id) return;

    try {
      setRemovingMember(memberId);
      setError(null);
      const token = await getToken();

      const response = await fetch(
        `${API_BASE_URL}/me/members?id=${memberId}`,
        {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${token}`,
            "X-Organization-ID": currentOrganization.id,
          },
        },
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || "Failed to remove member");
      }

      setSuccess("Member removed successfully");
      await fetchTeamData();
    } catch (err) {
      console.error("Error removing member:", err);
      setError(err instanceof Error ? err.message : "Failed to remove member");
    } finally {
      setRemovingMember(null);
    }
  }

  async function handleCancelInvite(inviteId: string) {
    if (!currentOrganization?.id) return;

    try {
      const token = await getToken();

      const response = await fetch(
        `${API_BASE_URL}/me/members?invite_id=${inviteId}`,
        {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${token}`,
            "X-Organization-ID": currentOrganization.id,
          },
        },
      );

      if (!response.ok) {
        throw new Error("Failed to cancel invite");
      }

      setSuccess("Invite cancelled");
      await fetchTeamData();
    } catch (err) {
      console.error("Error cancelling invite:", err);
      setError("Failed to cancel invite");
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-zinc-400" />
      </div>
    );
  }

  const isOwner = currentUserRole === "owner";
  const isAdmin = currentUserRole === "admin" || isOwner;

  const getRoleIcon = (role: string) => {
    if (role === "owner") return <Crown className="h-4 w-4 text-amber-500" />;
    if (role === "admin") return <Shield className="h-4 w-4 text-indigo-500" />;
    return <Users className="h-4 w-4 text-zinc-400" />;
  };

  const getRoleBadgeClass = (role: string) => {
    if (role === "owner")
      return "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400";
    if (role === "admin")
      return "bg-indigo-100 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-400";
    return "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-400";
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
            Team Management
          </h2>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
            Invite members, manage roles, and configure team permissions.
          </p>
        </div>
        {isAdmin && (
          <Button
            onClick={() => setShowInviteModal(true)}
            className="rounded-xl"
          >
            <UserPlus className="mr-2 h-4 w-4" />
            Invite Member
          </Button>
        )}
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

      {/* Members List */}
      <Card className="rounded-2xl border-zinc-200 dark:border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg">Members ({members.length})</CardTitle>
          <CardDescription>
            People with access to this organization
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {members.map((member) => (
              <div
                key={member.id}
                className="flex items-center justify-between py-4 first:pt-0 last:pb-0"
              >
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-full bg-gradient-to-br from-indigo-400 to-purple-500 flex items-center justify-center text-white font-medium">
                    {member.name?.charAt(0)?.toUpperCase() ||
                      member.email?.charAt(0)?.toUpperCase()}
                  </div>
                  <div>
                    <p className="font-medium text-zinc-900 dark:text-zinc-100">
                      {member.name}
                    </p>
                    <p className="text-sm text-zinc-500 dark:text-zinc-400">
                      {member.email}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${getRoleBadgeClass(member.role)}`}
                  >
                    {getRoleIcon(member.role)}
                    {member.role.charAt(0).toUpperCase() + member.role.slice(1)}
                  </span>

                  {isAdmin &&
                    member.role !== "owner" &&
                    member.user_id !== user?.uid && (
                      <div className="flex items-center gap-1">
                        <select
                          value={member.role}
                          onChange={(e) =>
                            handleChangeRole(member.id, e.target.value)
                          }
                          disabled={changingRole === member.id}
                          className="rounded-lg border border-zinc-200 bg-white px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-800"
                        >
                          <option value="member">Member</option>
                          <option value="admin">Admin</option>
                          {isOwner && <option value="owner">Owner</option>}
                        </select>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveMember(member.id)}
                          disabled={removingMember === member.id}
                          className="h-8 w-8 p-0 text-red-500 hover:bg-red-50 hover:text-red-600"
                        >
                          {removingMember === member.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                    )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Pending Invites */}
      {invites.length > 0 && (
        <Card className="rounded-2xl border-zinc-200 dark:border-zinc-800">
          <CardHeader>
            <CardTitle className="text-lg">
              Pending Invites ({invites.length})
            </CardTitle>
            <CardDescription>Invitations awaiting response</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {invites.map((invite) => (
                <div
                  key={invite.id}
                  className="flex items-center justify-between py-4 first:pt-0 last:pb-0"
                >
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center">
                      <Mail className="h-5 w-5 text-zinc-400" />
                    </div>
                    <div>
                      <p className="font-medium text-zinc-900 dark:text-zinc-100">
                        {invite.email}
                      </p>
                      <p className="text-sm text-zinc-500 dark:text-zinc-400">
                        Invited as {invite.role} · Expires{" "}
                        {new Date(invite.expires_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  {isAdmin && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleCancelInvite(invite.id)}
                      className="text-zinc-500 hover:text-red-500"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Invite Modal */}
      {showInviteModal && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-[200] bg-black/50"
            onClick={() => {
              setShowInviteModal(false);
              setInviteEmail("");
              setInviteRole("member");
            }}
          />
          {/* Modal */}
          <div className="fixed inset-0 z-[201] flex items-center justify-center pointer-events-none">
            <div className="w-full max-w-md rounded-2xl bg-white p-6 dark:bg-zinc-900 shadow-xl pointer-events-auto mx-4">
              <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                Add Team Member
              </h3>
              <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
                Add a user to your organization. They must already have an
                account.
              </p>

              <div className="mt-4 space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    Email Address
                  </label>
                  <Input
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="colleague@company.com"
                    className="rounded-xl"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    Role
                  </label>
                  <select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value)}
                    className="w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
                  >
                    <option value="member">
                      Member - Can view and create decisions
                    </option>
                    <option value="admin">
                      Admin - Can manage members and settings
                    </option>
                  </select>
                </div>
              </div>

              <div className="mt-6 flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowInviteModal(false);
                    setInviteEmail("");
                    setInviteRole("member");
                  }}
                  className="rounded-xl"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleInvite}
                  disabled={inviting || !inviteEmail.trim()}
                  className="rounded-xl"
                >
                  {inviting ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <UserPlus className="mr-2 h-4 w-4" />
                  )}
                  Add Member
                </Button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default TeamTab;
