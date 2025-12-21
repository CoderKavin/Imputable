"use client";

/**
 * Audit Export Page
 *
 * Enterprise feature for generating SOC2/ISO/HIPAA compliant audit reports.
 */

import { useState, useCallback } from "react";
import { AppLayout } from "@/components/app";
import { Button } from "@/components/ui/button";
import {
  Shield,
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
} from "lucide-react";

// =============================================================================
// TYPES
// =============================================================================

interface QuarterPreset {
  label: string;
  start_date: string;
  end_date: string;
}

interface DecisionPreview {
  decision_number: number;
  title: string;
  status: string;
  created_at: string;
  version_count: number;
}

interface ExportPreview {
  decision_count: number;
  date_range: string;
  filters_applied: {
    teams: number;
    tags: string[];
    status: string[];
  };
  estimated_pages: number;
  decisions_preview: DecisionPreview[];
}

// =============================================================================
// API FUNCTIONS
// =============================================================================

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

async function fetchPreview(
  startDate: string,
  endDate: string,
  tags?: string[],
  statusFilter?: string[],
): Promise<ExportPreview> {
  const response = await fetch(`${API_BASE}/audit-export/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      start_date: startDate,
      end_date: endDate,
      tags: tags?.length ? tags : undefined,
      status_filter: statusFilter?.length ? statusFilter : undefined,
    }),
  });
  if (!response.ok) throw new Error("Failed to fetch preview");
  return response.json();
}

async function generateReport(
  startDate: string,
  endDate: string,
  tags?: string[],
  statusFilter?: string[],
): Promise<{ blob: Blob; hash: string; filename: string }> {
  const response = await fetch(`${API_BASE}/audit-export/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      start_date: startDate,
      end_date: endDate,
      tags: tags?.length ? tags : undefined,
      status_filter: statusFilter?.length ? statusFilter : undefined,
    }),
  });

  if (!response.ok) throw new Error("Failed to generate report");

  const blob = await response.blob();
  const hash = response.headers.get("X-Verification-Hash") || "";
  const contentDisposition = response.headers.get("Content-Disposition") || "";
  const filenameMatch = contentDisposition.match(/filename="(.+)"/);
  const filename = filenameMatch ? filenameMatch[1] : "audit_report.pdf";

  return { blob, hash, filename };
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function AuditExportPage() {
  // Date selection state
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");

  // Filter state
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);

  // Preview and generation state
  const [preview, setPreview] = useState<ExportPreview | null>(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedHash, setGeneratedHash] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Presets
  const presets: QuarterPreset[] = getQuarterPresets();

  // Handle preset selection
  const handlePresetSelect = useCallback((preset: QuarterPreset) => {
    setSelectedPreset(preset.label);
    setStartDate(preset.start_date);
    setEndDate(preset.end_date);
    setPreview(null);
    setGeneratedHash(null);
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
      setPreview(null);
      setGeneratedHash(null);
    },
    [],
  );

  // Add tag
  const handleAddTag = useCallback(() => {
    const tag = tagInput.trim().toLowerCase();
    if (tag && !selectedTags.includes(tag)) {
      setSelectedTags((prev) => [...prev, tag]);
      setTagInput("");
      setPreview(null);
    }
  }, [tagInput, selectedTags]);

  // Remove tag
  const handleRemoveTag = useCallback((tag: string) => {
    setSelectedTags((prev) => prev.filter((t) => t !== tag));
    setPreview(null);
  }, []);

  // Toggle status filter
  const handleToggleStatus = useCallback((status: string) => {
    setSelectedStatuses((prev) =>
      prev.includes(status)
        ? prev.filter((s) => s !== status)
        : [...prev, status],
    );
    setPreview(null);
  }, []);

  // Fetch preview
  const handlePreview = useCallback(async () => {
    if (!startDate || !endDate) {
      setError("Please select a date range");
      return;
    }

    setIsLoadingPreview(true);
    setError(null);

    try {
      const previewData = await fetchPreview(
        startDate,
        endDate,
        selectedTags,
        selectedStatuses,
      );
      setPreview(previewData);
    } catch {
      setError("Failed to load preview. Please try again.");
    } finally {
      setIsLoadingPreview(false);
    }
  }, [startDate, endDate, selectedTags, selectedStatuses]);

  // Generate report
  const handleGenerate = useCallback(async () => {
    if (!startDate || !endDate) {
      setError("Please select a date range");
      return;
    }

    setIsGenerating(true);
    setError(null);

    try {
      const { blob, hash, filename } = await generateReport(
        startDate,
        endDate,
        selectedTags,
        selectedStatuses,
      );

      // Download the file
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      // Show the verification hash
      setGeneratedHash(hash);
    } catch {
      setError("Failed to generate report. Please try again.");
    } finally {
      setIsGenerating(false);
    }
  }, [startDate, endDate, selectedTags, selectedStatuses]);

  const statuses = [
    "draft",
    "pending_review",
    "approved",
    "deprecated",
    "superseded",
  ];

  return (
    <AppLayout
      title="Audit Export"
      subtitle="Generate compliance reports for SOC2, ISO 27001, and HIPAA audits"
    >
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column - Filters */}
        <div className="lg:col-span-2 space-y-6">
          {/* Date Range Selection */}
          <div className="bg-white rounded-3xl border border-gray-100 p-8">
            <h3 className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-6">
              <Calendar className="w-5 h-5 text-gray-400" />
              Date Range
            </h3>

            {/* Preset Buttons */}
            <div className="mb-6">
              <p className="text-sm font-medium text-gray-600 mb-3">
                Quick Select
              </p>
              <div className="flex flex-wrap gap-2">
                {presets.slice(0, 6).map((preset) => (
                  <button
                    key={preset.label}
                    onClick={() => handlePresetSelect(preset)}
                    className={`px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 ${
                      selectedPreset === preset.label
                        ? "bg-gray-900 text-white"
                        : "bg-gray-50 text-gray-600 hover:bg-gray-100 border border-gray-200"
                    }`}
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
                    value={startDate ? startDate.split("T")[0] : ""}
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
                    value={endDate ? endDate.split("T")[0] : ""}
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
          <div className="bg-white rounded-3xl border border-gray-100 p-8">
            <h3 className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-6">
              <Filter className="w-5 h-5 text-gray-400" />
              Filters (Optional)
            </h3>

            {/* Tags Filter */}
            <div className="mb-6">
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
                  placeholder="e.g., PaymentSystem, Security"
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
              {selectedTags.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {selectedTags.map((tag) => (
                    <span
                      key={tag}
                      onClick={() => handleRemoveTag(tag)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 text-gray-700 text-sm rounded-full cursor-pointer hover:bg-gray-200 transition-colors"
                    >
                      {tag}
                      <X className="w-3 h-3" />
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Status Filter */}
            <div>
              <p className="text-sm font-medium text-gray-600 mb-3">
                Filter by Status
              </p>
              <div className="flex flex-wrap gap-2">
                {statuses.map((status) => (
                  <button
                    key={status}
                    onClick={() => handleToggleStatus(status)}
                    className={`px-4 py-2 rounded-xl text-sm font-medium capitalize transition-all duration-200 ${
                      selectedStatuses.includes(status)
                        ? "bg-gray-900 text-white"
                        : "bg-gray-50 text-gray-600 hover:bg-gray-100 border border-gray-200"
                    }`}
                  >
                    {status.replace("_", " ")}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Preview Section */}
          {preview && (
            <div className="bg-white rounded-3xl border border-gray-100 p-8">
              <h3 className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-6">
                <Eye className="w-5 h-5 text-gray-400" />
                Preview
              </h3>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-4 mb-6">
                <div className="text-center p-5 bg-gray-50 rounded-2xl">
                  <p className="text-3xl font-bold text-indigo-600">
                    {preview.decision_count}
                  </p>
                  <p className="text-sm text-gray-500 mt-1">Decisions</p>
                </div>
                <div className="text-center p-5 bg-gray-50 rounded-2xl">
                  <p className="text-3xl font-bold text-indigo-600">
                    ~{preview.estimated_pages}
                  </p>
                  <p className="text-sm text-gray-500 mt-1">Pages</p>
                </div>
                <div className="text-center p-5 bg-gray-50 rounded-2xl">
                  <p className="text-sm font-medium text-gray-900">
                    {preview.date_range}
                  </p>
                  <p className="text-sm text-gray-500 mt-1">Date Range</p>
                </div>
              </div>

              {/* Decision List Preview */}
              <div>
                <p className="text-sm font-medium text-gray-600 mb-3">
                  Included Decisions (showing first 20)
                </p>
                <div className="max-h-64 overflow-y-auto border border-gray-100 rounded-2xl">
                  {preview.decisions_preview.map((decision, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between px-4 py-3 border-b border-gray-50 last:border-b-0"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          DEC-{decision.decision_number}: {decision.title}
                        </p>
                        <p className="text-xs text-gray-500">
                          {decision.version_count} version
                          {decision.version_count !== 1 ? "s" : ""}
                        </p>
                      </div>
                      <span
                        className={`ml-2 px-3 py-1 rounded-full text-xs font-semibold capitalize ${getStatusClasses(decision.status)}`}
                      >
                        {decision.status.replace("_", " ")}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Column - Actions */}
        <div className="space-y-6">
          {/* Generate Card */}
          <div className="bg-gradient-to-br from-indigo-50 to-white rounded-3xl border border-indigo-100 p-8">
            <div className="text-center mb-6">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-indigo-100 rounded-2xl mb-4">
                <FileText className="w-8 h-8 text-indigo-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">
                Generate Official Report
              </h3>
              <p className="text-sm text-gray-500 mt-1">
                Professional PDF with tamper-proof verification
              </p>
            </div>

            {/* Action Buttons */}
            <div className="space-y-3">
              <Button
                variant="outline"
                className="w-full rounded-2xl h-11"
                onClick={handlePreview}
                disabled={!startDate || !endDate || isLoadingPreview}
              >
                {isLoadingPreview ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Loading Preview...
                  </>
                ) : (
                  <>
                    <Eye className="w-4 h-4 mr-2" />
                    Preview Report
                  </>
                )}
              </Button>

              <Button
                className="w-full rounded-2xl h-11 bg-indigo-600 hover:bg-indigo-700"
                onClick={handleGenerate}
                disabled={!startDate || !endDate || isGenerating}
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Generating PDF...
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4 mr-2" />
                    Generate Official Report
                  </>
                )}
              </Button>
            </div>

            {/* Error */}
            {error && (
              <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-2xl">
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            {/* Verification Hash */}
            {generatedHash && (
              <div className="mt-4 p-4 bg-emerald-50 border border-emerald-200 rounded-2xl">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                  <p className="text-sm font-medium text-emerald-800">
                    Report Generated Successfully
                  </p>
                </div>
                <p className="text-xs text-emerald-700 mb-2">
                  Verification Hash (SHA-256):
                </p>
                <code className="block text-xs bg-white p-2 rounded-xl border border-emerald-200 text-emerald-800 break-all font-mono">
                  {generatedHash}
                </code>
                <p className="text-xs text-emerald-600 mt-2">
                  Save this hash to verify report authenticity later.
                </p>
              </div>
            )}
          </div>

          {/* Info Card */}
          <div className="bg-white rounded-3xl border border-gray-100 p-8">
            <h4 className="font-semibold text-gray-900 mb-4">
              What's Included
            </h4>
            <ul className="space-y-3 text-sm text-gray-600">
              {[
                "Cover page with organization details",
                "Table of contents",
                "Executive summary with statistics",
                "Full decision documentation",
                "Complete audit trail per decision",
                "Cryptographic verification hash",
              ].map((item, i) => (
                <li key={i} className="flex items-start gap-2">
                  <Check className="w-4 h-4 text-emerald-500 mt-0.5 flex-shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          {/* Compliance Info */}
          <div className="bg-amber-50 rounded-3xl border border-amber-200 p-6">
            <div className="flex items-start gap-3">
              <Info className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
              <div>
                <h4 className="font-semibold text-amber-800 mb-1">
                  Compliance Ready
                </h4>
                <p className="text-sm text-amber-700">
                  This report format is designed to meet documentation
                  requirements for SOC2, ISO 27001, and HIPAA audits.
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

  // Quarters
  const quarters = [
    { name: "Q1", start: 0, end: 2 },
    { name: "Q2", start: 3, end: 5 },
    { name: "Q3", start: 6, end: 8 },
    { name: "Q4", start: 9, end: 11 },
  ];

  for (const q of quarters) {
    const qStart = new Date(year, q.start, 1);
    const qEnd = new Date(year, q.end + 1, 0, 23, 59, 59);
    if (qStart <= now) {
      presets.push({
        label: `${q.name} ${year}`,
        start_date: qStart.toISOString(),
        end_date: qEnd > now ? now.toISOString() : qEnd.toISOString(),
      });
    }
  }

  return presets;
}

function getStatusClasses(status: string): string {
  switch (status) {
    case "approved":
      return "bg-emerald-50 text-emerald-700";
    case "deprecated":
    case "superseded":
      return "bg-gray-100 text-gray-600";
    case "draft":
      return "bg-gray-50 text-gray-600";
    case "pending_review":
      return "bg-amber-50 text-amber-700";
    default:
      return "bg-gray-50 text-gray-600";
  }
}
