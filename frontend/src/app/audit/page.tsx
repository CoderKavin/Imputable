"use client";

/**
 * Audit Export Page
 *
 * Enterprise feature for generating SOC2/ISO/HIPAA compliant audit reports.
 * Features:
 * - Date range selection with quarterly presets
 * - Team and tag filtering
 * - Preview before generation
 * - One-click PDF generation
 */

import { useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

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

async function fetchPresets(): Promise<QuarterPreset[]> {
  const response = await fetch(`${API_BASE}/audit-export/presets`, {
    credentials: "include",
  });
  if (!response.ok) throw new Error("Failed to fetch presets");
  return response.json();
}

async function fetchPreview(
  startDate: string,
  endDate: string,
  tags?: string[],
  statusFilter?: string[]
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
  statusFilter?: string[]
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
  const [useCustomRange, setUseCustomRange] = useState(false);

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

  // Presets (hardcoded for demo - would fetch from API)
  const presets: QuarterPreset[] = getQuarterPresets();

  // Handle preset selection
  const handlePresetSelect = useCallback((preset: QuarterPreset) => {
    setSelectedPreset(preset.label);
    setStartDate(preset.start_date);
    setEndDate(preset.end_date);
    setUseCustomRange(false);
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
      setUseCustomRange(true);
      setPreview(null);
      setGeneratedHash(null);
    },
    []
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
        : [...prev, status]
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
        selectedStatuses
      );
      setPreview(previewData);
    } catch (err) {
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
        selectedStatuses
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
    } catch (err) {
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
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-indigo-100 rounded-lg">
              <ShieldCheckIcon className="h-8 w-8 text-indigo-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Audit Export</h1>
              <p className="text-gray-500">
                Generate compliance reports for SOC2, ISO 27001, and HIPAA audits
              </p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column - Filters */}
          <div className="lg:col-span-2 space-y-6">
            {/* Date Range Selection */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CalendarIcon className="h-5 w-5 text-gray-500" />
                  Date Range
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Preset Buttons */}
                <div>
                  <p className="text-sm font-medium text-gray-700 mb-3">
                    Quick Select
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {presets.map((preset) => (
                      <Button
                        key={preset.label}
                        variant={
                          selectedPreset === preset.label ? "default" : "outline"
                        }
                        size="sm"
                        onClick={() => handlePresetSelect(preset)}
                      >
                        {preset.label}
                      </Button>
                    ))}
                  </div>
                </div>

                {/* Custom Date Range */}
                <div>
                  <p className="text-sm font-medium text-gray-700 mb-3">
                    Or select custom range
                  </p>
                  <div className="flex items-center gap-4">
                    <div className="flex-1">
                      <label className="block text-xs text-gray-500 mb-1">
                        Start Date
                      </label>
                      <input
                        type="date"
                        value={startDate ? startDate.split("T")[0] : ""}
                        onChange={(e) =>
                          handleCustomDateChange("start", e.target.value)
                        }
                        className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                    </div>
                    <span className="text-gray-400 mt-5">to</span>
                    <div className="flex-1">
                      <label className="block text-xs text-gray-500 mb-1">
                        End Date
                      </label>
                      <input
                        type="date"
                        value={endDate ? endDate.split("T")[0] : ""}
                        onChange={(e) =>
                          handleCustomDateChange("end", e.target.value)
                        }
                        className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Filters */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FilterIcon className="h-5 w-5 text-gray-500" />
                  Filters (Optional)
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Tags Filter */}
                <div>
                  <p className="text-sm font-medium text-gray-700 mb-2">
                    Filter by Tags
                  </p>
                  <div className="flex gap-2 mb-2">
                    <input
                      type="text"
                      value={tagInput}
                      onChange={(e) => setTagInput(e.target.value)}
                      onKeyDown={(e) =>
                        e.key === "Enter" && (e.preventDefault(), handleAddTag())
                      }
                      placeholder="e.g., PaymentSystem, Security"
                      className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                    <Button variant="outline" size="sm" onClick={handleAddTag}>
                      Add
                    </Button>
                  </div>
                  {selectedTags.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {selectedTags.map((tag) => (
                        <Badge
                          key={tag}
                          variant="secondary"
                          className="gap-1 cursor-pointer"
                          onClick={() => handleRemoveTag(tag)}
                        >
                          {tag}
                          <XIcon className="h-3 w-3" />
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>

                {/* Status Filter */}
                <div>
                  <p className="text-sm font-medium text-gray-700 mb-2">
                    Filter by Status
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {statuses.map((status) => (
                      <Button
                        key={status}
                        variant={
                          selectedStatuses.includes(status)
                            ? "default"
                            : "outline"
                        }
                        size="sm"
                        onClick={() => handleToggleStatus(status)}
                        className="capitalize"
                      >
                        {status.replace("_", " ")}
                      </Button>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Preview Section */}
            {preview && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <EyeIcon className="h-5 w-5 text-gray-500" />
                    Preview
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {/* Stats */}
                  <div className="grid grid-cols-3 gap-4 mb-6">
                    <div className="text-center p-4 bg-gray-50 rounded-lg">
                      <p className="text-3xl font-bold text-indigo-600">
                        {preview.decision_count}
                      </p>
                      <p className="text-sm text-gray-500">Decisions</p>
                    </div>
                    <div className="text-center p-4 bg-gray-50 rounded-lg">
                      <p className="text-3xl font-bold text-indigo-600">
                        ~{preview.estimated_pages}
                      </p>
                      <p className="text-sm text-gray-500">Pages</p>
                    </div>
                    <div className="text-center p-4 bg-gray-50 rounded-lg">
                      <p className="text-sm font-medium text-gray-900">
                        {preview.date_range}
                      </p>
                      <p className="text-sm text-gray-500">Date Range</p>
                    </div>
                  </div>

                  {/* Decision List Preview */}
                  <div>
                    <p className="text-sm font-medium text-gray-700 mb-2">
                      Included Decisions (showing first 20)
                    </p>
                    <div className="max-h-64 overflow-y-auto border border-gray-200 rounded-lg">
                      {preview.decisions_preview.map((decision, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between px-4 py-3 border-b last:border-b-0"
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
                          <Badge
                            variant={getStatusVariant(decision.status)}
                            className="ml-2 capitalize"
                          >
                            {decision.status.replace("_", " ")}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Right Column - Actions */}
          <div className="space-y-6">
            {/* Generate Card */}
            <Card className="bg-gradient-to-br from-indigo-50 to-white border-indigo-100">
              <CardContent className="pt-6">
                <div className="text-center mb-6">
                  <div className="inline-flex items-center justify-center w-16 h-16 bg-indigo-100 rounded-full mb-4">
                    <DocumentIcon className="h-8 w-8 text-indigo-600" />
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
                    className="w-full"
                    onClick={handlePreview}
                    disabled={!startDate || !endDate || isLoadingPreview}
                  >
                    {isLoadingPreview ? (
                      <>
                        <LoaderIcon className="h-4 w-4 mr-2 animate-spin" />
                        Loading Preview...
                      </>
                    ) : (
                      <>
                        <EyeIcon className="h-4 w-4 mr-2" />
                        Preview Report
                      </>
                    )}
                  </Button>

                  <Button
                    className="w-full bg-indigo-600 hover:bg-indigo-700"
                    onClick={handleGenerate}
                    disabled={!startDate || !endDate || isGenerating}
                  >
                    {isGenerating ? (
                      <>
                        <LoaderIcon className="h-4 w-4 mr-2 animate-spin" />
                        Generating PDF...
                      </>
                    ) : (
                      <>
                        <DownloadIcon className="h-4 w-4 mr-2" />
                        Generate Official Report
                      </>
                    )}
                  </Button>
                </div>

                {/* Error */}
                {error && (
                  <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                    <p className="text-sm text-red-700">{error}</p>
                  </div>
                )}

                {/* Verification Hash */}
                {generatedHash && (
                  <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <CheckCircleIcon className="h-5 w-5 text-green-600" />
                      <p className="text-sm font-medium text-green-800">
                        Report Generated Successfully
                      </p>
                    </div>
                    <p className="text-xs text-green-700 mb-2">
                      Verification Hash (SHA-256):
                    </p>
                    <code className="block text-xs bg-white p-2 rounded border border-green-200 text-green-800 break-all font-mono">
                      {generatedHash}
                    </code>
                    <p className="text-xs text-green-600 mt-2">
                      Save this hash to verify report authenticity later.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Info Card */}
            <Card>
              <CardContent className="pt-6">
                <h4 className="font-medium text-gray-900 mb-3">
                  What's Included
                </h4>
                <ul className="space-y-2 text-sm text-gray-600">
                  <li className="flex items-start gap-2">
                    <CheckIcon className="h-4 w-4 text-green-500 mt-0.5" />
                    Cover page with organization details
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckIcon className="h-4 w-4 text-green-500 mt-0.5" />
                    Table of contents
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckIcon className="h-4 w-4 text-green-500 mt-0.5" />
                    Executive summary with statistics
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckIcon className="h-4 w-4 text-green-500 mt-0.5" />
                    Full decision documentation
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckIcon className="h-4 w-4 text-green-500 mt-0.5" />
                    Complete audit trail per decision
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckIcon className="h-4 w-4 text-green-500 mt-0.5" />
                    Cryptographic verification hash
                  </li>
                </ul>
              </CardContent>
            </Card>

            {/* Compliance Info */}
            <Card className="bg-amber-50 border-amber-200">
              <CardContent className="pt-6">
                <div className="flex items-start gap-3">
                  <InfoIcon className="h-5 w-5 text-amber-600 mt-0.5" />
                  <div>
                    <h4 className="font-medium text-amber-800 mb-1">
                      Compliance Ready
                    </h4>
                    <p className="text-sm text-amber-700">
                      This report format is designed to meet documentation
                      requirements for SOC2, ISO 27001, and HIPAA audits.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
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

  // Quarters for current and last year
  const quarters = [
    { name: "Q1", start: 0, end: 2 },
    { name: "Q2", start: 3, end: 5 },
    { name: "Q3", start: 6, end: 8 },
    { name: "Q4", start: 9, end: 11 },
  ];

  for (const y of [year, year - 1]) {
    for (const q of quarters) {
      const qStart = new Date(y, q.start, 1);
      const qEnd = new Date(y, q.end + 1, 0, 23, 59, 59);
      if (qStart <= now) {
        presets.push({
          label: `${q.name} ${y}`,
          start_date: qStart.toISOString(),
          end_date: qEnd > now ? now.toISOString() : qEnd.toISOString(),
        });
      }
    }
  }

  return presets;
}

function getStatusVariant(
  status: string
): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "approved":
      return "default";
    case "deprecated":
    case "superseded":
      return "destructive";
    case "draft":
    case "pending_review":
      return "secondary";
    default:
      return "outline";
  }
}

// =============================================================================
// ICONS
// =============================================================================

function ShieldCheckIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
      />
    </svg>
  );
}

function CalendarIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
      />
    </svg>
  );
}

function FilterIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
      />
    </svg>
  );
}

function EyeIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
      />
    </svg>
  );
}

function DocumentIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
      />
    </svg>
  );
}

function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
      />
    </svg>
  );
}

function LoaderIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
      />
    </svg>
  );
}

function CheckCircleIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  );
}

function InfoIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M6 18L18 6M6 6l12 12"
      />
    </svg>
  );
}
