"use client";

import { useState, useRef, useEffect } from "react";
import { useOrganization } from "@/contexts/OrganizationContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function OrganizationSwitcher() {
  const {
    organizations,
    currentOrganization,
    loading,
    switchOrganization,
    createOrganization
  } = useOrganization();

  const [isOpen, setIsOpen] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newOrgName, setNewOrgName] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setShowCreateForm(false);
        setNewOrgName("");
        setError(null);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSwitchOrg = (orgId: string) => {
    switchOrganization(orgId);
    setIsOpen(false);
  };

  const handleCreateOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newOrgName.trim()) return;

    setCreating(true);
    setError(null);

    try {
      // Generate slug from name
      const slug = newOrgName
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "");

      await createOrganization(newOrgName, slug);
      setNewOrgName("");
      setShowCreateForm(false);
      setIsOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create organization");
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return (
      <div className="h-9 w-40 rounded-lg bg-gray-200 animate-pulse" />
    );
  }

  if (!currentOrganization && organizations.length === 0) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => {
          setIsOpen(true);
          setShowCreateForm(true);
        }}
      >
        Create Organization
      </Button>
    );
  }

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 min-w-[160px]"
      >
        <div className="h-6 w-6 rounded bg-primary/10 text-primary flex items-center justify-center text-xs font-medium">
          {currentOrganization?.name?.charAt(0).toUpperCase() || "O"}
        </div>
        <span className="text-sm font-medium text-gray-900 truncate flex-1 text-left">
          {currentOrganization?.name || "Select Organization"}
        </span>
        <svg
          className={`w-4 h-4 text-gray-500 transition-transform ${isOpen ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute left-0 mt-2 w-64 rounded-lg bg-white shadow-lg border border-gray-200 py-1 z-50">
          {!showCreateForm ? (
            <>
              <div className="px-3 py-2 border-b border-gray-100">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Organizations
                </p>
              </div>

              <div className="max-h-60 overflow-y-auto py-1">
                {organizations.map((org) => (
                  <button
                    key={org.id}
                    onClick={() => handleSwitchOrg(org.id)}
                    className={`w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-gray-100 ${
                      currentOrganization?.id === org.id ? "bg-gray-50" : ""
                    }`}
                  >
                    <div className="h-6 w-6 rounded bg-primary/10 text-primary flex items-center justify-center text-xs font-medium">
                      {org.name.charAt(0).toUpperCase()}
                    </div>
                    <span className="text-sm text-gray-900 truncate flex-1">
                      {org.name}
                    </span>
                    {currentOrganization?.id === org.id && (
                      <svg className="w-4 h-4 text-primary" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    )}
                  </button>
                ))}
              </div>

              <div className="border-t border-gray-100 py-1">
                <button
                  onClick={() => setShowCreateForm(true)}
                  className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-100"
                >
                  <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  Create new organization
                </button>
              </div>
            </>
          ) : (
            <div className="p-3">
              <p className="text-sm font-medium text-gray-900 mb-3">Create Organization</p>
              <form onSubmit={handleCreateOrg}>
                {error && (
                  <div className="mb-3 text-sm text-red-600 bg-red-50 px-3 py-2 rounded">
                    {error}
                  </div>
                )}
                <Input
                  type="text"
                  placeholder="Organization name"
                  value={newOrgName}
                  onChange={(e) => setNewOrgName(e.target.value)}
                  disabled={creating}
                  className="mb-3"
                  autoFocus
                />
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setShowCreateForm(false);
                      setNewOrgName("");
                      setError(null);
                    }}
                    disabled={creating}
                    className="flex-1"
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    size="sm"
                    disabled={creating || !newOrgName.trim()}
                    className="flex-1"
                  >
                    {creating ? "Creating..." : "Create"}
                  </Button>
                </div>
              </form>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
