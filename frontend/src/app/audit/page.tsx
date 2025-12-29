"use client";

/**
 * Audit Log Page
 *
 * Shows real audit trail of all actions in the organization.
 * Also provides compliance report generation for SOC2/ISO/HIPAA audits.
 */

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppLayout } from "@/components/app";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { useOrganization } from "@/contexts/OrganizationContext";
import { useDecisionList } from "@/hooks/use-decisions";
import { useApiClient } from "@/hooks/use-api";
import { useQuery } from "@tanstack/react-query";
import {
  Calendar,
  Filter,
  Eye,
  FileText,
  Download,
  Loader2,
  CheckCircle2,
  Check,
  Info,
  X,
  Clock,
  AlertTriangle,
  Shield,
  BarChart3,
  Users,
  Tag,
  ArrowRight,
  RefreshCw,
  Activity,
  User,
  Edit,
  Plus,
  Trash2,
} from "lucide-react";
import { cn } from "@/lib/utils";

// Audit log entry type
interface AuditLogEntry {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  details: Record<string, unknown>;
  created_at: string;
  user: {
    id: string;
    name: string;
    email: string;
  } | null;
}

// =============================================================================
// TYPES
// =============================================================================

interface QuarterPreset {
  label: string;
  start_date: string;
  end_date: string;
}

interface DecisionPreview {
  id: string;
  decision_number: number;
  title: string;
  status: string;
  created_at: string;
  tags: string[];
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function AuditExportPage() {
  const router = useRouter();
  const { user, getToken } = useAuth();
  const { currentOrganization } = useOrganization();
  const apiClient = useApiClient();

  // Tab state - show audit log or report generator
  const [activeTab, setActiveTab] = useState<"log" | "report">("log");

  // Fetch audit log entries
  const {
    data: auditData,
    isLoading: auditLoading,
    refetch: refetchAudit,
  } = useQuery({
    queryKey: ["audit-log", currentOrganization?.id],
    queryFn: async () => {
      const response = await apiClient.get("/audit", {
        params: { page: 1, page_size: 50 },
      });
      return response.data as {
        items: AuditLogEntry[];
        total: number;
        page: number;
        page_size: number;
      };
    },
    enabled: !!user && !!currentOrganization?.id,
    staleTime: 30_000,
  });

  // Fetch decisions for report generation
  const {
    data: decisionsData,
    isLoading: decisionsLoading,
    refetch,
  } = useDecisionList(1, 100);

  // Date selection state
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");

  // Filter state
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);

  // Generation state
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedHash, setGeneratedHash] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Auto-select "Last 30 Days" on mount
  useEffect(() => {
    const presets = getQuarterPresets();
    if (presets.length > 0 && !selectedPreset) {
      handlePresetSelect(presets[0]);
    }
  }, []);

  // Presets
  const presets: QuarterPreset[] = getQuarterPresets();

  // Filter decisions based on date range and filters
  const filteredDecisions =
    decisionsData?.items?.filter((decision) => {
      // Date filter
      if (startDate && decision.created_at) {
        const decisionDate = new Date(decision.created_at);
        const start = new Date(startDate);
        if (decisionDate < start) return false;
      }
      if (endDate && decision.created_at) {
        const decisionDate = new Date(decision.created_at);
        const end = new Date(endDate);
        if (decisionDate > end) return false;
      }

      // Status filter
      if (
        selectedStatuses.length > 0 &&
        !selectedStatuses.includes(decision.status)
      ) {
        return false;
      }

      // Tag filter
      if (selectedTags.length > 0) {
        const decisionTags = decision.tags || [];
        const hasMatchingTag = selectedTags.some((tag) =>
          decisionTags.some((dt: string) =>
            dt.toLowerCase().includes(tag.toLowerCase()),
          ),
        );
        if (!hasMatchingTag) return false;
      }

      return true;
    }) || [];

  // Calculate stats for decisions
  const decisionStats = {
    total: filteredDecisions.length,
    approved: filteredDecisions.filter((d) => d.status === "approved").length,
    pending: filteredDecisions.filter((d) => d.status === "pending_review")
      .length,
    draft: filteredDecisions.filter((d) => d.status === "draft").length,
  };

  // Calculate stats for audit log
  const auditStats = {
    total: auditData?.total || 0,
    creates: auditData?.items?.filter((a) => a.action === "create").length || 0,
    updates: auditData?.items?.filter((a) => a.action === "update").length || 0,
    reads: auditData?.items?.filter((a) => a.action === "read").length || 0,
  };

  // Get all unique tags from decisions
  const allTags = Array.from(
    new Set(decisionsData?.items?.flatMap((d) => d.tags || []) || []),
  ).slice(0, 20);

  // Handle preset selection
  const handlePresetSelect = useCallback((preset: QuarterPreset) => {
    setSelectedPreset(preset.label);
    setStartDate(preset.start_date.split("T")[0]);
    setEndDate(preset.end_date.split("T")[0]);
    setGeneratedHash(null);
    setError(null);
  }, []);

  // Handle custom date change
  const handleCustomDateChange = useCallback(
    (type: "start" | "end", value: string) => {
      if (type === "start") {
        setStartDate(value);
      } else {
        setEndDate(value);
      }
      setSelectedPreset(null);
      setGeneratedHash(null);
      setError(null);
    },
    [],
  );

  // Add tag
  const handleAddTag = useCallback(() => {
    const tag = tagInput.trim().toLowerCase();
    if (tag && !selectedTags.includes(tag)) {
      setSelectedTags((prev) => [...prev, tag]);
      setTagInput("");
    }
  }, [tagInput, selectedTags]);

  // Remove tag
  const handleRemoveTag = useCallback((tag: string) => {
    setSelectedTags((prev) => prev.filter((t) => t !== tag));
  }, []);

  // Toggle status filter
  const handleToggleStatus = useCallback((status: string) => {
    setSelectedStatuses((prev) =>
      prev.includes(status)
        ? prev.filter((s) => s !== status)
        : [...prev, status],
    );
  }, []);

  // Generate report (client-side for now - creates a summary JSON)
  const handleGenerate = useCallback(async () => {
    if (!startDate || !endDate) {
      setError("Please select a date range");
      return;
    }

    if (filteredDecisions.length === 0) {
      setError(
        "No decisions match your filters. Adjust the date range or filters.",
      );
      return;
    }

    setIsGenerating(true);
    setError(null);

    try {
      // Create a comprehensive audit report
      const report = {
        metadata: {
          organization: currentOrganization?.name || "Unknown",
          generated_at: new Date().toISOString(),
          generated_by: user?.email || "Unknown",
          date_range: {
            start: startDate,
            end: endDate,
          },
          filters: {
            statuses: selectedStatuses.length > 0 ? selectedStatuses : "All",
            tags: selectedTags.length > 0 ? selectedTags : "All",
          },
        },
        summary: {
          total_decisions: filteredDecisions.length,
          by_status: decisionStats,
        },
        decisions: filteredDecisions.map((d) => ({
          decision_number: d.decision_number,
          title: d.title,
          status: d.status,
          created_at: d.created_at,
          tags: d.tags || [],
        })),
      };

      // Generate a hash for verification
      const reportString = JSON.stringify(report);
      const encoder = new TextEncoder();
      const data = encoder.encode(reportString);
      const hashBuffer = await crypto.subtle.digest("SHA-256", data);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      const hash = hashArray
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");

      // Download the report as JSON
      const blob = new Blob([JSON.stringify(report, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `audit_report_${currentOrganization?.slug || "org"}_${startDate}_${endDate}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      setGeneratedHash(hash);
    } catch (err) {
      setError("Failed to generate report. Please try again.");
      console.error("Report generation error:", err);
    } finally {
      setIsGenerating(false);
    }
  }, [
    startDate,
    endDate,
    filteredDecisions,
    currentOrganization,
    user,
    selectedStatuses,
    selectedTags,
    decisionStats,
  ]);

  const statuses = [
    "draft",
    "pending_review",
    "approved",
    "deprecated",
    "superseded",
  ];

  // Redirect if not authenticated
  useEffect(() => {
    if (!user && !decisionsLoading) {
      router.push("/sign-in");
    }
  }, [user, decisionsLoading, router]);

  // Show empty state if no organization selected
  if (!currentOrganization) {
    return (
      <AppLayout
        title="Audit Log"
        subtitle="Generate compliance reports for SOC2, ISO 27001, and HIPAA audits"
      >
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="text-center max-w-md">
            <div className="w-16 h-16 rounded-2xl bg-amber-100 flex items-center justify-center mx-auto mb-6">
              <Shield className="w-8 h-8 text-amber-600" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              No Organization Selected
            </h2>
            <p className="text-gray-500 mb-8">
              To generate audit reports, you need to be part of an organization.
              Use the organization switcher in the header to create or join one.
            </p>
          </div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout
      title="Audit Log"
      subtitle="Generate compliance reports for SOC2, ISO 27001, and HIPAA audits"
    >
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column - Filters & Preview */}
        <div className="lg:col-span-2 space-y-6">
          {/* Stats Overview */}
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-white rounded-2xl border border-gray-100 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Total</p>
                  <p className="text-2xl font-bold text-gray-900 mt-1">
                    {decisionsLoading ? "..." : decisionStats.total}
                  </p>
                </div>
                <div className="w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center">
                  <FileText className="w-5 h-5 text-indigo-600" />
                </div>
              </div>
            </div>
            <div className="bg-white rounded-2xl border border-gray-100 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Approved</p>
                  <p className="text-2xl font-bold text-emerald-600 mt-1">
                    {decisionsLoading ? "..." : decisionStats.approved}
                  </p>
                </div>
                <div className="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                </div>
              </div>
            </div>
            <div className="bg-white rounded-2xl border border-gray-100 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Pending</p>
                  <p className="text-2xl font-bold text-amber-600 mt-1">
                    {decisionsLoading ? "..." : decisionStats.pending}
                  </p>
                </div>
                <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center">
                  <Clock className="w-5 h-5 text-amber-600" />
                </div>
              </div>
            </div>
            <div className="bg-white rounded-2xl border border-gray-100 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Draft</p>
                  <p className="text-2xl font-bold text-gray-600 mt-1">
                    {decisionsLoading ? "..." : decisionStats.draft}
                  </p>
                </div>
                <div className="w-10 h-10 rounded-xl bg-gray-100 flex items-center justify-center">
                  <FileText className="w-5 h-5 text-gray-500" />
                </div>
              </div>
            </div>
          </div>

          {/* Date Range Selection */}
          <div className="bg-white rounded-2xl border border-gray-100 p-6">
            <h3 className="flex items-center gap-2 text-base font-semibold text-gray-900 mb-5">
              <Calendar className="w-5 h-5 text-indigo-500" />
              Date Range
            </h3>

            {/* Preset Buttons */}
            <div className="mb-5">
              <p className="text-sm font-medium text-gray-600 mb-3">
                Quick Select
              </p>
              <div className="flex flex-wrap gap-2">
                {presets.map((preset) => (
                  <button
                    key={preset.label}
                    onClick={() => handlePresetSelect(preset)}
                    className={cn(
                      "px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200",
                      selectedPreset === preset.label
                        ? "bg-indigo-600 text-white shadow-lg shadow-indigo-500/25"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200",
                    )}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Custom Date Range */}
            <div>
              <p className="text-sm font-medium text-gray-600 mb-3">
                Or select custom range
              </p>
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <label className="block text-xs text-gray-500 mb-1.5">
                    Start Date
                  </label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) =>
                      handleCustomDateChange("start", e.target.value)
                    }
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 transition-all"
                  />
                </div>
                <span className="text-gray-400 mt-5">to</span>
                <div className="flex-1">
                  <label className="block text-xs text-gray-500 mb-1.5">
                    End Date
                  </label>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) =>
                      handleCustomDateChange("end", e.target.value)
                    }
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 transition-all"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Filters */}
          <div className="bg-white rounded-2xl border border-gray-100 p-6">
            <h3 className="flex items-center gap-2 text-base font-semibold text-gray-900 mb-5">
              <Filter className="w-5 h-5 text-indigo-500" />
              Filters
            </h3>

            {/* Status Filter */}
            <div className="mb-5">
              <p className="text-sm font-medium text-gray-600 mb-3">
                Filter by Status
              </p>
              <div className="flex flex-wrap gap-2">
                {statuses.map((status) => (
                  <button
                    key={status}
                    onClick={() => handleToggleStatus(status)}
                    className={cn(
                      "px-4 py-2 rounded-xl text-sm font-medium capitalize transition-all duration-200",
                      selectedStatuses.includes(status)
                        ? "bg-indigo-600 text-white"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200",
                    )}
                  >
                    {status.replace("_", " ")}
                  </button>
                ))}
                {selectedStatuses.length > 0 && (
                  <button
                    onClick={() => setSelectedStatuses([])}
                    className="px-3 py-2 text-sm text-gray-500 hover:text-gray-700"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>

            {/* Tags Filter */}
            <div>
              <p className="text-sm font-medium text-gray-600 mb-3">
                Filter by Tags
              </p>
              <div className="flex gap-2 mb-3">
                <input
                  type="text"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={(e) =>
                    e.key === "Enter" && (e.preventDefault(), handleAddTag())
                  }
                  placeholder="Type a tag and press Enter"
                  className="flex-1 px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 transition-all"
                />
                <Button
                  variant="outline"
                  onClick={handleAddTag}
                  className="rounded-xl"
                >
                  Add
                </Button>
              </div>

              {/* Selected tags */}
              {selectedTags.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-3">
                  {selectedTags.map((tag) => (
                    <span
                      key={tag}
                      onClick={() => handleRemoveTag(tag)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-100 text-indigo-700 text-sm rounded-full cursor-pointer hover:bg-indigo-200 transition-colors"
                    >
                      {tag}
                      <X className="w-3 h-3" />
                    </span>
                  ))}
                </div>
              )}

              {/* Suggested tags */}
              {allTags.length > 0 && (
                <div>
                  <p className="text-xs text-gray-500 mb-2">Suggested tags:</p>
                  <div className="flex flex-wrap gap-1.5">
                    {allTags
                      .filter(
                        (tag) => !selectedTags.includes(tag.toLowerCase()),
                      )
                      .slice(0, 10)
                      .map((tag) => (
                        <button
                          key={tag}
                          onClick={() =>
                            setSelectedTags((prev) => [
                              ...prev,
                              tag.toLowerCase(),
                            ])
                          }
                          className="px-2.5 py-1 text-xs text-gray-600 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors"
                        >
                          + {tag}
                        </button>
                      ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Preview Section */}
          <div className="bg-white rounded-2xl border border-gray-100 p-6">
            <div className="flex items-center justify-between mb-5">
              <h3 className="flex items-center gap-2 text-base font-semibold text-gray-900">
                <Eye className="w-5 h-5 text-indigo-500" />
                Preview ({filteredDecisions.length} decisions)
              </h3>
              <button
                onClick={() => refetch()}
                className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700"
              >
                <RefreshCw className="w-4 h-4" />
                Refresh
              </button>
            </div>

            {decisionsLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
              </div>
            ) : filteredDecisions.length === 0 ? (
              <div className="text-center py-12">
                <FileText className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                <p className="text-sm font-medium text-gray-900 mb-1">
                  No decisions found
                </p>
                <p className="text-xs text-gray-500">
                  Try adjusting your date range or filters
                </p>
              </div>
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {filteredDecisions.slice(0, 20).map((decision) => (
                  <div
                    key={decision.id}
                    className="flex items-center gap-4 p-3 rounded-xl hover:bg-gray-50 transition-colors cursor-pointer"
                    onClick={() => router.push(`/decisions/${decision.id}`)}
                  >
                    <div className="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center">
                      <FileText className="w-4 h-4 text-gray-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs text-gray-500">
                          DECISION-{decision.decision_number}
                        </span>
                        <span
                          className={cn(
                            "px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase",
                            getStatusClasses(decision.status),
                          )}
                        >
                          {decision.status.replace("_", " ")}
                        </span>
                      </div>
                      <p className="text-sm text-gray-900 truncate">
                        {decision.title}
                      </p>
                    </div>
                    <ArrowRight className="w-4 h-4 text-gray-300" />
                  </div>
                ))}
                {filteredDecisions.length > 20 && (
                  <p className="text-center text-xs text-gray-500 py-2">
                    + {filteredDecisions.length - 20} more decisions
                  </p>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right Column - Actions */}
        <div className="space-y-6">
          {/* Generate Card */}
          <div className="bg-gradient-to-br from-indigo-600 to-indigo-700 rounded-2xl p-6 text-white">
            <div className="text-center mb-6">
              <div className="inline-flex items-center justify-center w-14 h-14 bg-white/20 rounded-2xl mb-4">
                <Shield className="w-7 h-7 text-white" />
              </div>
              <h3 className="text-lg font-semibold">Generate Audit Report</h3>
              <p className="text-sm text-indigo-200 mt-1">
                Export compliance-ready documentation
              </p>
            </div>

            <Button
              className="w-full rounded-xl h-12 bg-white text-indigo-600 hover:bg-indigo-50 font-semibold"
              onClick={handleGenerate}
              disabled={
                !startDate ||
                !endDate ||
                isGenerating ||
                filteredDecisions.length === 0
              }
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Download className="w-5 h-5 mr-2" />
                  Download Report
                </>
              )}
            </Button>

            {!startDate || !endDate ? (
              <p className="text-xs text-indigo-200 text-center mt-3">
                Select a date range to generate
              </p>
            ) : filteredDecisions.length === 0 ? (
              <p className="text-xs text-indigo-200 text-center mt-3">
                No decisions match your filters
              </p>
            ) : (
              <p className="text-xs text-indigo-200 text-center mt-3">
                {filteredDecisions.length} decisions will be included
              </p>
            )}
          </div>

          {/* Error */}
          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-2xl">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-red-500 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-red-800">Error</p>
                  <p className="text-sm text-red-700 mt-0.5">{error}</p>
                </div>
              </div>
            </div>
          )}

          {/* Success */}
          {generatedHash && (
            <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl">
              <div className="flex items-center gap-2 mb-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                <p className="text-sm font-semibold text-emerald-800">
                  Report Generated!
                </p>
              </div>
              <p className="text-xs text-emerald-700 mb-2">
                Verification Hash (SHA-256):
              </p>
              <code className="block text-[10px] bg-white p-2 rounded-lg border border-emerald-200 text-emerald-800 break-all font-mono">
                {generatedHash}
              </code>
              <p className="text-xs text-emerald-600 mt-2">
                Save this hash to verify report authenticity.
              </p>
            </div>
          )}

          {/* Info Card */}
          <div className="bg-white rounded-2xl border border-gray-100 p-6">
            <h4 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-indigo-500" />
              What&apos;s Included
            </h4>
            <ul className="space-y-3 text-sm text-gray-600">
              {[
                "Organization metadata",
                "Date range and filter summary",
                "Decision statistics breakdown",
                "Full decision list with status",
                "Tags and categorization",
                "SHA-256 verification hash",
              ].map((item, i) => (
                <li key={i} className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          {/* Compliance Info */}
          <div className="bg-amber-50 rounded-2xl border border-amber-200 p-5">
            <div className="flex items-start gap-3">
              <Info className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
              <div>
                <h4 className="font-semibold text-amber-800 mb-1">
                  Compliance Ready
                </h4>
                <p className="text-sm text-amber-700">
                  Reports include cryptographic verification for SOC2, ISO
                  27001, and HIPAA compliance documentation.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

function getQuarterPresets(): QuarterPreset[] {
  const now = new Date();
  const year = now.getFullYear();
  const presets: QuarterPreset[] = [];

  // Last 30 days
  const last30 = new Date(now);
  last30.setDate(last30.getDate() - 30);
  presets.push({
    label: "Last 30 Days",
    start_date: last30.toISOString(),
    end_date: now.toISOString(),
  });

  // Last 90 days
  const last90 = new Date(now);
  last90.setDate(last90.getDate() - 90);
  presets.push({
    label: "Last 90 Days",
    start_date: last90.toISOString(),
    end_date: now.toISOString(),
  });

  // Year to date
  presets.push({
    label: `YTD ${year}`,
    start_date: new Date(year, 0, 1).toISOString(),
    end_date: now.toISOString(),
  });

  // Current quarter
  const currentQuarter = Math.floor(now.getMonth() / 3);
  const qStart = new Date(year, currentQuarter * 3, 1);
  presets.push({
    label: `Q${currentQuarter + 1} ${year}`,
    start_date: qStart.toISOString(),
    end_date: now.toISOString(),
  });

  // Last year
  presets.push({
    label: `${year - 1}`,
    start_date: new Date(year - 1, 0, 1).toISOString(),
    end_date: new Date(year - 1, 11, 31).toISOString(),
  });

  return presets;
}

function getStatusClasses(status: string): string {
  switch (status) {
    case "approved":
      return "bg-emerald-100 text-emerald-700";
    case "deprecated":
      return "bg-red-100 text-red-700";
    case "superseded":
      return "bg-purple-100 text-purple-700";
    case "draft":
      return "bg-gray-100 text-gray-600";
    case "pending_review":
      return "bg-amber-100 text-amber-700";
    default:
      return "bg-gray-100 text-gray-600";
  }
}
