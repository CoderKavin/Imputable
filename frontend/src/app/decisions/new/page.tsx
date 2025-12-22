"use client";

/**
 * Create New Decision Page
 *
 * Route: /decisions/new
 * Form for creating a new engineering decision record
 */

import React, { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useOrganization } from "@/contexts/OrganizationContext";
import { cn } from "@/lib/utils";
import { useCreateDecision } from "@/hooks/use-decisions";
import { AppLayout } from "@/components/app";
import { Button } from "@/components/ui/button";
import type {
  ImpactLevel,
  Alternative,
  CreateDecisionRequest,
} from "@/types/decision";
import {
  ArrowLeft,
  Save,
  Loader2,
  AlertCircle,
  FileText,
  CheckCircle2,
  Brain,
  XCircle,
  AlertTriangle,
  Plus,
  Trash2,
  Tag,
  X,
} from "lucide-react";

export default function NewDecisionPage() {
  const router = useRouter();
  const { currentOrganization } = useOrganization();
  const createMutation = useCreateDecision();

  // Form state
  const [title, setTitle] = useState("");
  const [context, setContext] = useState("");
  const [choice, setChoice] = useState("");
  const [rationale, setRationale] = useState("");
  const [consequences, setConsequences] = useState("");
  const [alternatives, setAlternatives] = useState<Alternative[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [impactLevel, setImpactLevel] = useState<ImpactLevel>("medium");
  const [tagInput, setTagInput] = useState("");

  // Handle form submission
  const handleSubmit = useCallback(async () => {
    if (
      !title.trim() ||
      !context.trim() ||
      !choice.trim() ||
      !rationale.trim()
    ) {
      return;
    }

    const createData: CreateDecisionRequest = {
      title,
      content: {
        context,
        choice,
        rationale,
        alternatives: alternatives.filter((a) => a.name.trim()),
        consequences: consequences || undefined,
      },
      impact_level: impactLevel,
      tags,
    };

    try {
      const newDecision = await createMutation.mutateAsync(createData);
      router.push(`/decisions/${newDecision.id}`);
    } catch (error) {
      console.error("Failed to create decision:", error);
    }
  }, [
    title,
    context,
    choice,
    rationale,
    alternatives,
    consequences,
    impactLevel,
    tags,
    createMutation,
    router,
  ]);

  // Add alternative
  const handleAddAlternative = useCallback(() => {
    setAlternatives((prev) => [...prev, { name: "", rejected_reason: "" }]);
  }, []);

  // Remove alternative
  const handleRemoveAlternative = useCallback((index: number) => {
    setAlternatives((prev) => prev.filter((_, i) => i !== index));
  }, []);

  // Update alternative
  const handleUpdateAlternative = useCallback(
    (index: number, field: "name" | "rejected_reason", value: string) => {
      setAlternatives((prev) =>
        prev.map((alt, i) => (i === index ? { ...alt, [field]: value } : alt)),
      );
    },
    [],
  );

  // Add tag
  const handleAddTag = useCallback(() => {
    const tag = tagInput.trim().toLowerCase();
    if (tag && !tags.includes(tag)) {
      setTags((prev) => [...prev, tag]);
      setTagInput("");
    }
  }, [tagInput, tags]);

  // Remove tag
  const handleRemoveTag = useCallback((tag: string) => {
    setTags((prev) => prev.filter((t) => t !== tag));
  }, []);

  const isValid =
    title.trim() && context.trim() && choice.trim() && rationale.trim();

  if (!currentOrganization) {
    return (
      <AppLayout
        title="Create Decision"
        subtitle="Document a new engineering decision"
      >
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="text-center">
            <AlertCircle className="w-12 h-12 mx-auto mb-4 text-amber-500" />
            <h2 className="text-xl font-semibold mb-2">
              No Organization Selected
            </h2>
            <p className="text-gray-500 mb-4">
              Please select an organization to create decisions.
            </p>
            <Button variant="outline" onClick={() => router.push("/dashboard")}>
              Go to Dashboard
            </Button>
          </div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout
      title="Create Decision"
      subtitle="Document a new engineering decision"
      actions={
        <Button
          variant="outline"
          onClick={() => router.back()}
          className="rounded-xl gap-2"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </Button>
      }
    >
      <div className="max-w-3xl mx-auto">
        <div className="bg-white rounded-3xl border border-gray-200 shadow-sm overflow-hidden">
          {/* Form */}
          <div className="p-6 space-y-6">
            {/* Title */}
            <FormSection icon={FileText} title="Title" required>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., Adopt PostgreSQL for primary database"
                className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 transition-all"
              />
            </FormSection>

            {/* Impact Level */}
            <FormSection icon={AlertTriangle} title="Impact Level" required>
              <div className="flex gap-2">
                {(["low", "medium", "high", "critical"] as ImpactLevel[]).map(
                  (level) => (
                    <button
                      key={level}
                      type="button"
                      onClick={() => setImpactLevel(level)}
                      className={cn(
                        "px-4 py-2 rounded-xl text-sm font-medium capitalize transition-all",
                        impactLevel === level
                          ? "bg-gray-900 text-white"
                          : "bg-gray-50 text-gray-600 hover:bg-gray-100 border border-gray-200",
                      )}
                    >
                      {level}
                    </button>
                  ),
                )}
              </div>
            </FormSection>

            {/* Context */}
            <FormSection
              icon={FileText}
              title="Context"
              description="What is the issue that we're seeing that is motivating this decision?"
              required
            >
              <textarea
                value={context}
                onChange={(e) => setContext(e.target.value)}
                rows={4}
                placeholder="Describe the background, problem statement, and any constraints..."
                className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 transition-all"
              />
            </FormSection>

            {/* Decision */}
            <FormSection
              icon={CheckCircle2}
              title="Decision"
              description="What is the change that we're proposing and/or doing?"
              required
            >
              <textarea
                value={choice}
                onChange={(e) => setChoice(e.target.value)}
                rows={3}
                placeholder="Clearly state the decision that was made..."
                className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 transition-all"
              />
            </FormSection>

            {/* Rationale */}
            <FormSection
              icon={Brain}
              title="Rationale"
              description="Why is this change being proposed? What are the pros and cons?"
              required
            >
              <textarea
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
                rows={4}
                placeholder="Explain the reasoning behind this decision..."
                className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 transition-all"
              />
            </FormSection>

            {/* Alternatives */}
            <FormSection
              icon={XCircle}
              title="Alternatives Considered"
              description="What other options were considered and why were they rejected?"
            >
              <div className="space-y-3">
                {alternatives.map((alt, index) => (
                  <div key={index} className="flex gap-2 items-start">
                    <div className="flex-1 space-y-2">
                      <input
                        type="text"
                        value={alt.name}
                        onChange={(e) =>
                          handleUpdateAlternative(index, "name", e.target.value)
                        }
                        placeholder="Alternative name"
                        className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 transition-all"
                      />
                      <input
                        type="text"
                        value={alt.rejected_reason}
                        onChange={(e) =>
                          handleUpdateAlternative(
                            index,
                            "rejected_reason",
                            e.target.value,
                          )
                        }
                        placeholder="Why it was rejected"
                        className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 transition-all"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveAlternative(index)}
                      className="p-2 rounded-xl text-red-500 hover:bg-red-50 transition-colors"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleAddAlternative}
                  className="rounded-xl"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Add Alternative
                </Button>
              </div>
            </FormSection>

            {/* Consequences */}
            <FormSection
              icon={AlertTriangle}
              title="Consequences"
              description="What are the expected outcomes of this decision?"
            >
              <textarea
                value={consequences}
                onChange={(e) => setConsequences(e.target.value)}
                rows={3}
                placeholder="Describe positive and negative consequences..."
                className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 transition-all"
              />
            </FormSection>

            {/* Tags */}
            <FormSection icon={Tag} title="Tags">
              <div className="space-y-3">
                {tags.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {tags.map((tag) => (
                      <span
                        key={tag}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 text-gray-700 text-sm rounded-full"
                      >
                        {tag}
                        <button
                          type="button"
                          onClick={() => handleRemoveTag(tag)}
                          className="hover:text-red-600 transition-colors"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                )}
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={tagInput}
                    onChange={(e) => setTagInput(e.target.value)}
                    onKeyDown={(e) =>
                      e.key === "Enter" && (e.preventDefault(), handleAddTag())
                    }
                    placeholder="Add tag (e.g., database, security, api)..."
                    className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 transition-all"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleAddTag}
                    className="rounded-xl"
                  >
                    Add
                  </Button>
                </div>
              </div>
            </FormSection>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between p-6 border-t border-gray-100 bg-gray-50/50">
            <p className="text-xs text-gray-500">
              All required fields must be filled to create the decision.
            </p>
            <div className="flex gap-3">
              <Button
                variant="outline"
                onClick={() => router.back()}
                className="rounded-xl"
              >
                Cancel
              </Button>
              <Button
                onClick={handleSubmit}
                disabled={!isValid || createMutation.isPending}
                className="rounded-xl"
              >
                {createMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Save className="h-4 w-4 mr-2" />
                    Create Decision
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* Error display */}
          {createMutation.isError && (
            <div className="mx-6 mb-6 p-4 rounded-2xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center gap-2">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              {(createMutation.error as Error).message ||
                "Failed to create decision"}
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}

// =============================================================================
// HELPER COMPONENTS
// =============================================================================

interface FormSectionProps {
  icon: React.ElementType;
  title: string;
  description?: string;
  required?: boolean;
  children: React.ReactNode;
}

function FormSection({
  icon: Icon,
  title,
  description,
  required,
  children,
}: FormSectionProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 text-gray-400" />
        <h4 className="font-medium text-sm text-gray-900">{title}</h4>
        {required && (
          <span className="text-xs font-medium px-2 py-0.5 bg-red-100 text-red-700 rounded-full">
            Required
          </span>
        )}
      </div>
      {description && <p className="text-xs text-gray-500">{description}</p>}
      {children}
    </div>
  );
}
