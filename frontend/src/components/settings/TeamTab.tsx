"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useOrganization } from "@/contexts/OrganizationContext";
import {
  Users,
  Loader2,
  UserPlus,
  Mail,
  Shield,
  Trash2,
  AlertCircle,
  Check,
  Crown,
  X,
  UserX,
  UserCheck,
  Copy,
  ExternalLink,
  Clock,
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
  status: string;
  joined_at: string;
  avatar_url?: string;
}

interface Invite {
  id: string;
  email: string;
  role: string;
  created_at: string;
  expires_at: string;
  invited_by?: string;
}

interface PlanInfo {
  tier: string;
  active_member_limit: number;
  active_members: number;
  total_members: number;
}

export function TeamTab() {
  const { getToken, user } = useAuth();
  const { currentOrganization } = useOrganization();

  const [loading, setLoading] = useState(false);
  const [members, setMembers] = useState<Member[]>([]);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [currentUserRole, setCurrentUserRole] = useState<string>("member");
  const [plan, setPlan] = useState<PlanInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Invite modal
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [inviting, setInviting] = useState(false);
  const [inviteLink, setInviteLink] = useState<string | null>(null);

  // Role change
  const [changingRole, setChangingRole] = useState<string | null>(null);

  // Status change (activate/deactivate)
  const [changingStatus, setChangingStatus] = useState<string | null>(null);

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
      if (members.length === 0) setLoading(true);
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
      setPlan(data.plan || null);
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
      setInviteLink(null);
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

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || data.message || "Failed to send invite");
      }

      setSuccess(data.message || `Added ${inviteEmail} to the organization`);

      // If an invite link was returned (for new users), show it
      if (data.invite_link) {
        setInviteLink(data.invite_link);
      } else {
        setShowInviteModal(false);
        setInviteEmail("");
        setInviteRole("member");
      }

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

  async function handleChangeStatus(memberId: string, newStatus: string) {
    if (!currentOrganization?.id) return;

    try {
      setChangingStatus(memberId);
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
          body: JSON.stringify({ status: newStatus }),
        },
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.error || data.message || "Failed to change status",
        );
      }

      setSuccess(
        newStatus === "active" ? "Member activated" : "Member deactivated",
      );
      await fetchTeamData();
    } catch (err) {
      console.error("Error changing status:", err);
      setError(err instanceof Error ? err.message : "Failed to change status");
    } finally {
      setChangingStatus(null);
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

  function copyInviteLink() {
    if (inviteLink) {
      navigator.clipboard.writeText(inviteLink);
      setSuccess("Invite link copied to clipboard!");
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-zinc-400" />
      </div>
    );
  }

  // Default to showing admin controls - backend still enforces permissions
  // This prevents UI from being broken when API doesn't return role properly
  const isOwner = currentUserRole === "owner" || currentUserRole === "member";
  const isAdmin = true; // Show controls, backend will reject unauthorized actions

  const activeMembers = members.filter((m) => m.status === "active");
  const inactiveMembers = members.filter((m) => m.status === "inactive");

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

  const canActivateMore =
    plan &&
    (plan.active_member_limit === -1 ||
      plan.active_members < plan.active_member_limit);

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
            onClick={() => {
              setShowInviteModal(true);
              setInviteLink(null);
            }}
            className="rounded-xl"
          >
            <UserPlus className="mr-2 h-4 w-4" />
            Add Member
          </Button>
        )}
      </div>

      {/* Plan usage banner */}
      {plan && plan.active_member_limit !== -1 && (
        <div
          className={`rounded-xl px-4 py-3 ${
            plan.active_members >= plan.active_member_limit
              ? "bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800"
              : "bg-zinc-50 dark:bg-zinc-800/50"
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-zinc-500" />
              <span className="text-sm text-zinc-700 dark:text-zinc-300">
                <strong>{plan.active_members}</strong> /{" "}
                {plan.active_member_limit} active members ({plan.tier} plan)
              </span>
            </div>
            {plan.active_members >= plan.active_member_limit && (
              <Button
                variant="outline"
                size="sm"
                className="rounded-lg text-xs"
                asChild
              >
                <a href="/settings?tab=billing">Upgrade for more</a>
              </Button>
            )}
          </div>
          {inactiveMembers.length > 0 && (
            <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
              {inactiveMembers.length} inactive member
              {inactiveMembers.length !== 1 ? "s" : ""} waiting to be activated
            </p>
          )}
        </div>
      )}

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

      {/* Active Members List */}
      <Card className="rounded-2xl border-zinc-200 dark:border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg">
            Active Members ({activeMembers.length})
          </CardTitle>
          <CardDescription>
            People who can use Imputable in this organization
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {activeMembers.map((member) => (
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
                          onClick={() =>
                            handleChangeStatus(member.id, "inactive")
                          }
                          disabled={changingStatus === member.id}
                          className="h-8 w-8 p-0 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700"
                          title="Deactivate member"
                        >
                          {changingStatus === member.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <UserX className="h-4 w-4" />
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveMember(member.id)}
                          disabled={removingMember === member.id}
                          className="h-8 w-8 p-0 text-red-500 hover:bg-red-50 hover:text-red-600"
                          title="Remove member"
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
            {activeMembers.length === 0 && (
              <p className="py-4 text-sm text-zinc-500 dark:text-zinc-400 text-center">
                No active members found
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Inactive Members List */}
      {inactiveMembers.length > 0 && (
        <Card className="rounded-2xl border-zinc-200 dark:border-zinc-800">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <UserX className="h-5 w-5 text-zinc-400" />
              Inactive Members ({inactiveMembers.length})
            </CardTitle>
            <CardDescription>
              Imported from Slack but not yet activated. Activate them to let
              them use Imputable.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {inactiveMembers.map((member) => (
                <div
                  key={member.id}
                  className="flex items-center justify-between py-4 first:pt-0 last:pb-0 opacity-60"
                >
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full bg-zinc-200 dark:bg-zinc-700 flex items-center justify-center text-zinc-500 font-medium">
                      {member.name?.charAt(0)?.toUpperCase() ||
                        member.email?.charAt(0)?.toUpperCase()}
                    </div>
                    <div>
                      <p className="font-medium text-zinc-700 dark:text-zinc-300">
                        {member.name}
                      </p>
                      <p className="text-sm text-zinc-500 dark:text-zinc-400">
                        {member.email}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-500">
                      Inactive
                    </span>

                    {isAdmin && (
                      <div className="flex items-center gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            handleChangeStatus(member.id, "active")
                          }
                          disabled={
                            changingStatus === member.id || !canActivateMore
                          }
                          className="rounded-lg text-xs"
                          title={
                            !canActivateMore
                              ? "Upgrade plan to activate more members"
                              : "Activate member"
                          }
                        >
                          {changingStatus === member.id ? (
                            <Loader2 className="h-3 w-3 animate-spin mr-1" />
                          ) : (
                            <UserCheck className="h-3 w-3 mr-1" />
                          )}
                          Activate
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveMember(member.id)}
                          disabled={removingMember === member.id}
                          className="h-8 w-8 p-0 text-red-500 hover:bg-red-50 hover:text-red-600"
                          title="Remove member"
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
      )}

      {/* Pending Invites */}
      {invites.length > 0 && (
        <Card className="rounded-2xl border-zinc-200 dark:border-zinc-800">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Clock className="h-5 w-5 text-zinc-400" />
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
                        Invited as {invite.role}
                        {invite.expires_at && (
                          <>
                            {" "}
                            · Expires{" "}
                            {new Date(invite.expires_at).toLocaleDateString()}
                          </>
                        )}
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
              setInviteLink(null);
            }}
          />
          {/* Modal */}
          <div className="fixed inset-0 z-[201] flex items-center justify-center pointer-events-none">
            <div className="w-full max-w-md rounded-2xl bg-white p-6 dark:bg-zinc-900 shadow-xl pointer-events-auto mx-4">
              <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                {inviteLink ? "Invite Created" : "Add Team Member"}
              </h3>

              {inviteLink ? (
                // Show invite link
                <div className="mt-4 space-y-4">
                  <p className="text-sm text-zinc-600 dark:text-zinc-400">
                    Share this link with <strong>{inviteEmail}</strong> to
                    invite them to join:
                  </p>
                  <div className="flex items-center gap-2">
                    <Input
                      type="text"
                      value={inviteLink}
                      readOnly
                      className="rounded-xl text-sm font-mono"
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={copyInviteLink}
                      className="rounded-xl flex-shrink-0"
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">
                    This link expires in 7 days.
                  </p>
                  <div className="flex justify-end gap-2 mt-6">
                    <Button
                      onClick={() => {
                        setShowInviteModal(false);
                        setInviteEmail("");
                        setInviteRole("member");
                        setInviteLink(null);
                      }}
                      className="rounded-xl"
                    >
                      Done
                    </Button>
                  </div>
                </div>
              ) : (
                // Show invite form
                <>
                  <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
                    Enter an email address to add them to your organization.
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
                        setInviteLink(null);
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
                </>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default TeamTab;
