"use client";

/**
 * Propose Change Modal
 *
 * Interface for amending a decision (creating a new version).
 * Modern rounded design with improved UX.
 */

import React, { useState, useCallback, useEffect } from "react";
import { cn } from "@/lib/utils";
import { useDecision, useAmendDecision } from "@/hooks/use-decisions";
import { Button } from "@/components/ui/button";
import type {
  ImpactLevel,
  AmendDecisionRequest,
  Alternative,
} from "@/types/decision";
import {
  X,
  Save,
  Loader2,
  AlertCircle,
  FileText,
  CheckCircle2,
  Brain,
  XCircle,
  AlertTriangle,
  MessageSquare,
  Plus,
  Trash2,
  Tag,
} from "lucide-react";

interface ProposeChangeModalProps {
  decisionId: string;
  onClose: () => void;
  onSuccess?: () => void;
}

export function ProposeChangeModal({
  decisionId,
  onClose,
  onSuccess,
}: ProposeChangeModalProps) {
  const { data: decision, isLoading: isLoadingDecision } =
    useDecision(decisionId);
  const amendMutation = useAmendDecision(decisionId);

  // Form state
  const [title, setTitle] = useState("");
  const [context, setContext] = useState("");
  const [choice, setChoice] = useState("");
  const [rationale, setRationale] = useState("");
  const [consequences, setConsequences] = useState("");
  const [alternatives, setAlternatives] = useState<Alternative[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [impactLevel, setImpactLevel] = useState<ImpactLevel>("medium");
  const [changeReason, setChangeReason] = useState("");
  const [tagInput, setTagInput] = useState("");

  // Initialize form with current decision content
  useEffect(() => {
    if (decision) {
      const content = decision.version.content;
      setTitle(decision.version.title);
      setContext(content.context);
      setChoice(content.choice);
      setRationale(content.rationale);
      setConsequences(content.consequences || "");
      setAlternatives(content.alternatives || []);
      setTags(decision.version.tags || []);
      setImpactLevel(decision.version.impact_level);
    }
  }, [decision]);

  // Handle form submission
  const handleSubmit = useCallback(async () => {
    if (!decision || !changeReason.trim()) {
      return;
    }

    const amendData: AmendDecisionRequest = {
      title,
      content: {
        context,
        choice,
        rationale,
        alternatives,
        consequences: consequences || undefined,
      },
      impact_level: impactLevel,
      tags,
      change_summary: changeReason,
      expected_version: decision.version.version_number,
    };

    try {
      await amendMutation.mutateAsync(amendData);
      onSuccess?.();
      onClose();
    } catch (error) {
      console.error("Failed to propose change:", error);
    }
  }, [
    decision,
    title,
    context,
    choice,
    rationale,
    alternatives,
    consequences,
    impactLevel,
    tags,
    changeReason,
    amendMutation,
    onSuccess,
    onClose,
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

  if (isLoadingDecision) {
    return (
      <ModalWrapper onClose={onClose}>
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-indigo-600" />
        </div>
      </ModalWrapper>
    );
  }

  if (!decision) {
    return (
      <ModalWrapper onClose={onClose}>
        <div className="text-center py-16">
          <AlertCircle className="h-12 w-12 mx-auto mb-4 text-red-500" />
          <p className="text-gray-600">Failed to load decision</p>
        </div>
      </ModalWrapper>
    );
  }

  const isValid =
    title.trim() &&
    context.trim() &&
    choice.trim() &&
    rationale.trim() &&
    changeReason.trim();

  return (
    <ModalWrapper onClose={onClose}>
      {/* Header */}
      <div className="flex items-center justify-between p-6 border-b border-gray-100">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">
            Propose Change
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            DEC-{decision.decision_number} · Creating v
            {decision.version.version_number + 1}
          </p>
        </div>
        <button
          onClick={onClose}
          className="w-8 h-8 rounded-xl flex items-center justify-center hover:bg-gray-100 transition-colors"
        >
          <X className="h-5 w-5 text-gray-500" />
        </button>
      </div>

      {/* Form */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Change Reason - REQUIRED */}
        <div className="bg-indigo-50 rounded-2xl border border-indigo-100 p-5">
          <div className="flex items-center gap-2 mb-3">
            <MessageSquare className="h-5 w-5 text-indigo-600" />
            <h3 className="font-semibold text-gray-900">Change Reason</h3>
            <span className="text-xs font-medium px-2 py-0.5 bg-red-100 text-red-700 rounded-full">
              Required
            </span>
          </div>
          <p className="text-xs text-gray-600 mb-3">
            Explain what you&apos;re changing and why. This will be recorded in
            the audit log.
          </p>
          <textarea
            value={changeReason}
            onChange={(e) => setChangeReason(e.target.value)}
            placeholder="e.g., Updating rationale due to new Q3 budget constraints..."
            className="w-full h-24 px-4 py-3 rounded-xl border border-indigo-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 transition-all placeholder:text-gray-400"
          />
        </div>

        {/* Title */}
        <FormSection icon={FileText} title="Title">
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 transition-all"
          />
        </FormSection>

        {/* Impact Level */}
        <FormSection icon={AlertTriangle} title="Impact Level">
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
          description="Background and problem statement"
        >
          <textarea
            value={context}
            onChange={(e) => setContext(e.target.value)}
            rows={4}
            className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 transition-all"
          />
        </FormSection>

        {/* Decision */}
        <FormSection
          icon={CheckCircle2}
          title="Decision"
          description="What we decided"
        >
          <textarea
            value={choice}
            onChange={(e) => setChoice(e.target.value)}
            rows={3}
            className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 transition-all"
          />
        </FormSection>

        {/* Rationale */}
        <FormSection
          icon={Brain}
          title="Rationale"
          description="Why we made this choice"
        >
          <textarea
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
            rows={4}
            className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 transition-all"
          />
        </FormSection>

        {/* Alternatives */}
        <FormSection
          icon={XCircle}
          title="Alternatives Considered"
          description="Options we rejected"
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
          description="Expected outcomes (optional)"
        >
          <textarea
            value={consequences}
            onChange={(e) => setConsequences(e.target.value)}
            rows={3}
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
                placeholder="Add tag..."
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
          This will create version {decision.version.version_number + 1}. The
          current version will be preserved.
        </p>
        <div className="flex gap-3">
          <Button variant="outline" onClick={onClose} className="rounded-xl">
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!isValid || amendMutation.isPending}
            className="rounded-xl"
          >
            {amendMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="h-4 w-4 mr-2" />
                Save New Version
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Error display */}
      {amendMutation.isError && (
        <div className="absolute bottom-24 left-6 right-6 p-4 rounded-2xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center gap-2">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {(amendMutation.error as Error).message || "Failed to save changes"}
        </div>
      )}
    </ModalWrapper>
  );
}

// =============================================================================
// HELPER COMPONENTS
// =============================================================================

function ModalWrapper({
  children,
  onClose,
}: {
  children: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      {/* Modal */}
      <div className="relative w-full max-w-3xl max-h-[90vh] bg-white rounded-3xl shadow-2xl flex flex-col overflow-hidden">
        {children}
      </div>
    </div>
  );
}

interface FormSectionProps {
  icon: React.ElementType;
  title: string;
  description?: string;
  children: React.ReactNode;
}

function FormSection({
  icon: Icon,
  title,
  description,
  children,
}: FormSectionProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 text-gray-400" />
        <h4 className="font-medium text-sm text-gray-900">{title}</h4>
      </div>
      {description && <p className="text-xs text-gray-500">{description}</p>}
      {children}
    </div>
  );
}

export default ProposeChangeModal;
