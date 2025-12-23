"use client";

import { useState, useEffect, useRef } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useOrganization } from "@/contexts/OrganizationContext";
import { Users, X, ChevronDown, Check, Loader2 } from "lucide-react";

interface Member {
  id: string;
  user_id: string;
  email: string;
  name: string;
  role: string;
  avatar_url?: string;
}

interface ReviewerPickerProps {
  selectedIds: string[];
  onChange: (ids: string[]) => void;
  excludeCurrentUser?: boolean;
  placeholder?: string;
}

export function ReviewerPicker({
  selectedIds,
  onChange,
  excludeCurrentUser = true,
  placeholder = "Select reviewers...",
}: ReviewerPickerProps) {
  const { getToken, user } = useAuth();
  const { currentOrganization } = useOrganization();
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Fetch org members
  useEffect(() => {
    async function fetchMembers() {
      if (!currentOrganization) return;

      setLoading(true);
      setError(null);

      try {
        const token = await getToken();
        const response = await fetch("/api/v1/me/members", {
          headers: {
            Authorization: `Bearer ${token}`,
            "X-Organization-ID": currentOrganization.id,
          },
        });

        if (!response.ok) {
          throw new Error("Failed to fetch members");
        }

        const data = await response.json();
        setMembers(data.members || []);
      } catch (err) {
        setError("Failed to load team members");
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    fetchMembers();
  }, [currentOrganization, getToken]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Filter members based on search and exclude current user
  const filteredMembers = members.filter((member) => {
    if (excludeCurrentUser && member.email === user?.email) {
      return false;
    }
    if (search) {
      const searchLower = search.toLowerCase();
      return (
        member.name.toLowerCase().includes(searchLower) ||
        member.email.toLowerCase().includes(searchLower)
      );
    }
    return true;
  });

  // Get selected members for display
  const selectedMembers = members.filter((m) =>
    selectedIds.includes(m.user_id),
  );

  // Toggle selection
  const toggleMember = (userId: string) => {
    if (selectedIds.includes(userId)) {
      onChange(selectedIds.filter((id) => id !== userId));
    } else {
      onChange([...selectedIds, userId]);
    }
  };

  // Remove a selected member
  const removeMember = (userId: string) => {
    onChange(selectedIds.filter((id) => id !== userId));
  };

  // Get initials for avatar
  const getInitials = (name: string) => {
    if (!name) return "??";
    return (
      name
        .split(" ")
        .filter((n) => n.length > 0)
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2) || "??"
    );
  };

  // Get deterministic color for avatar
  const getAvatarColor = (name: string) => {
    const colors = [
      "bg-indigo-500",
      "bg-purple-500",
      "bg-pink-500",
      "bg-blue-500",
      "bg-emerald-500",
      "bg-amber-500",
    ];
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
      hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    return colors[Math.abs(hash) % colors.length];
  };

  return (
    <div ref={dropdownRef} className="relative">
      {/* Label */}
      <label className="block text-sm font-medium text-gray-700 mb-2">
        <Users className="w-4 h-4 inline mr-2" />
        Reviewers
        <span className="text-gray-400 font-normal ml-1">(optional)</span>
      </label>

      {/* Selected reviewers pills */}
      {selectedMembers.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2">
          {selectedMembers.map((member) => (
            <span
              key={member.user_id}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-indigo-50 text-indigo-700 rounded-lg text-sm"
            >
              <span
                className={`w-5 h-5 rounded-full flex items-center justify-center text-white text-xs ${getAvatarColor(member.name)}`}
              >
                {getInitials(member.name)}
              </span>
              {member.name}
              <button
                type="button"
                onClick={() => removeMember(member.user_id)}
                className="ml-0.5 hover:bg-indigo-100 rounded p-0.5"
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Dropdown trigger */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-white border border-gray-200 rounded-xl text-sm hover:border-gray-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 transition-all"
      >
        <span className="text-gray-500">
          {selectedIds.length === 0
            ? placeholder
            : `${selectedIds.length} reviewer${selectedIds.length > 1 ? "s" : ""} selected`}
        </span>
        {loading ? (
          <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
        ) : (
          <ChevronDown
            className={`w-4 h-4 text-gray-400 transition-transform ${isOpen ? "rotate-180" : ""}`}
          />
        )}
      </button>

      {/* Dropdown menu */}
      {isOpen && (
        <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden">
          {/* Search input */}
          <div className="p-2 border-b border-gray-100">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search team members..."
              className="w-full px-3 py-2 text-sm bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300"
              autoFocus
            />
          </div>

          {/* Members list */}
          <div className="max-h-60 overflow-y-auto">
            {error ? (
              <div className="px-4 py-3 text-sm text-red-600">{error}</div>
            ) : filteredMembers.length === 0 ? (
              <div className="px-4 py-3 text-sm text-gray-500">
                {search
                  ? "No matching members found"
                  : "No team members available"}
              </div>
            ) : (
              filteredMembers.map((member) => {
                const isSelected = selectedIds.includes(member.user_id);
                return (
                  <button
                    key={member.user_id}
                    type="button"
                    onClick={() => toggleMember(member.user_id)}
                    className={`w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-gray-50 transition-colors ${
                      isSelected ? "bg-indigo-50" : ""
                    }`}
                  >
                    <span
                      className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-medium ${getAvatarColor(member.name)}`}
                    >
                      {getInitials(member.name)}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-900 truncate">
                        {member.name}
                      </div>
                      <div className="text-xs text-gray-500 truncate">
                        {member.email}
                      </div>
                    </div>
                    {isSelected && (
                      <Check className="w-4 h-4 text-indigo-600 flex-shrink-0" />
                    )}
                  </button>
                );
              })
            )}
          </div>

          {/* Footer hint */}
          {filteredMembers.length > 0 && (
            <div className="px-4 py-2 border-t border-gray-100 bg-gray-50">
              <p className="text-xs text-gray-500">
                Selected reviewers will be notified and asked to approve the
                decision.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
