"use client";

/**
 * Propose Change Modal
 *
 * Interface for amending a decision (creating a new version).
 * Key features:
 * - Pre-filled with current content
 * - Required "Change Reason" field
 * - Rich text editing with TipTap
 * - Optimistic locking with expected_version
 */

import React, { useState, useCallback, useEffect } from "react";
import { cn } from "@/lib/utils";
import { useDecision, useAmendDecision } from "@/hooks/use-decisions";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type {
  DecisionContent,
  ImpactLevel,
  AmendDecisionRequest,
  Alternative
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
  const { data: decision, isLoading: isLoadingDecision } = useDecision(decisionId);
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
      // Error handled by mutation
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
    setAlternatives((prev) => [
      ...prev,
      { name: "", rejected_reason: "" },
    ]);
  }, []);

  // Remove alternative
  const handleRemoveAlternative = useCallback((index: number) => {
    setAlternatives((prev) => prev.filter((_, i) => i !== index));
  }, []);

  // Update alternative
  const handleUpdateAlternative = useCallback(
    (index: number, field: "name" | "rejected_reason", value: string) => {
      setAlternatives((prev) =>
        prev.map((alt, i) =>
          i === index ? { ...alt, [field]: value } : alt
        )
      );
    },
    []
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
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      </ModalWrapper>
    );
  }

  if (!decision) {
    return (
      <ModalWrapper onClose={onClose}>
        <div className="text-center py-12 text-destructive">
          <AlertCircle className="h-12 w-12 mx-auto mb-4" />
          <p>Failed to load decision</p>
        </div>
      </ModalWrapper>
    );
  }

  const isValid = title.trim() && context.trim() && choice.trim() &&
                  rationale.trim() && changeReason.trim();

  return (
    <ModalWrapper onClose={onClose}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b">
        <div>
          <h2 className="text-lg font-semibold">Propose Change</h2>
          <p className="text-sm text-muted-foreground">
            DEC-{decision.decision_number} · Creating v{decision.version.version_number + 1}
          </p>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Form */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Change Reason - REQUIRED */}
        <Card className="border-primary/30 bg-primary/5">
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5 text-primary" />
              <h3 className="font-semibold">Change Reason</h3>
              <Badge variant="destructive" className="text-xs">Required</Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              Explain what you're changing and why. This will be recorded in the audit log.
            </p>
          </CardHeader>
          <CardContent>
            <textarea
              value={changeReason}
              onChange={(e) => setChangeReason(e.target.value)}
              placeholder="e.g., Updating rationale due to new Q3 budget constraints..."
              className={cn(
                "w-full h-24 px-3 py-2 rounded-md border bg-background text-sm",
                "focus:outline-none focus:ring-2 focus:ring-primary/20",
                "placeholder:text-muted-foreground"
              )}
            />
          </CardContent>
        </Card>

        {/* Title */}
        <FormSection icon={FileText} title="Title">
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className={cn(
              "w-full px-3 py-2 rounded-md border bg-background text-sm",
              "focus:outline-none focus:ring-2 focus:ring-primary/20"
            )}
          />
        </FormSection>

        {/* Impact Level */}
        <FormSection icon={AlertTriangle} title="Impact Level">
          <div className="flex gap-2">
            {(["low", "medium", "high", "critical"] as ImpactLevel[]).map((level) => (
              <Button
                key={level}
                type="button"
                variant={impactLevel === level ? "default" : "outline"}
                size="sm"
                onClick={() => setImpactLevel(level)}
                className="capitalize"
              >
                {level}
              </Button>
            ))}
          </div>
        </FormSection>

        {/* Context */}
        <FormSection icon={FileText} title="Context" description="Background and problem statement">
          <textarea
            value={context}
            onChange={(e) => setContext(e.target.value)}
            rows={4}
            className={cn(
              "w-full px-3 py-2 rounded-md border bg-background text-sm",
              "focus:outline-none focus:ring-2 focus:ring-primary/20"
            )}
          />
        </FormSection>

        {/* Decision */}
        <FormSection icon={CheckCircle2} title="Decision" description="What we decided">
          <textarea
            value={choice}
            onChange={(e) => setChoice(e.target.value)}
            rows={3}
            className={cn(
              "w-full px-3 py-2 rounded-md border bg-background text-sm",
              "focus:outline-none focus:ring-2 focus:ring-primary/20"
            )}
          />
        </FormSection>

        {/* Rationale */}
        <FormSection icon={Brain} title="Rationale" description="Why we made this choice">
          <textarea
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
            rows={4}
            className={cn(
              "w-full px-3 py-2 rounded-md border bg-background text-sm",
              "focus:outline-none focus:ring-2 focus:ring-primary/20"
            )}
          />
        </FormSection>

        {/* Alternatives */}
        <FormSection icon={XCircle} title="Alternatives Considered" description="Options we rejected">
          <div className="space-y-3">
            {alternatives.map((alt, index) => (
              <div key={index} className="flex gap-2 items-start">
                <div className="flex-1 space-y-2">
                  <input
                    type="text"
                    value={alt.name}
                    onChange={(e) => handleUpdateAlternative(index, "name", e.target.value)}
                    placeholder="Alternative name"
                    className={cn(
                      "w-full px-3 py-2 rounded-md border bg-background text-sm",
                      "focus:outline-none focus:ring-2 focus:ring-primary/20"
                    )}
                  />
                  <input
                    type="text"
                    value={alt.rejected_reason}
                    onChange={(e) => handleUpdateAlternative(index, "rejected_reason", e.target.value)}
                    placeholder="Why it was rejected"
                    className={cn(
                      "w-full px-3 py-2 rounded-md border bg-background text-sm",
                      "focus:outline-none focus:ring-2 focus:ring-primary/20"
                    )}
                  />
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => handleRemoveAlternative(index)}
                  className="text-destructive hover:text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleAddAlternative}
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Alternative
            </Button>
          </div>
        </FormSection>

        {/* Consequences */}
        <FormSection icon={AlertTriangle} title="Consequences" description="Expected outcomes (optional)">
          <textarea
            value={consequences}
            onChange={(e) => setConsequences(e.target.value)}
            rows={3}
            className={cn(
              "w-full px-3 py-2 rounded-md border bg-background text-sm",
              "focus:outline-none focus:ring-2 focus:ring-primary/20"
            )}
          />
        </FormSection>

        {/* Tags */}
        <FormSection icon={FileText} title="Tags">
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              {tags.map((tag) => (
                <Badge key={tag} variant="secondary" className="gap-1">
                  {tag}
                  <button
                    type="button"
                    onClick={() => handleRemoveTag(tag)}
                    className="ml-1 hover:text-destructive"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), handleAddTag())}
                placeholder="Add tag..."
                className={cn(
                  "flex-1 px-3 py-2 rounded-md border bg-background text-sm",
                  "focus:outline-none focus:ring-2 focus:ring-primary/20"
                )}
              />
              <Button type="button" variant="outline" size="sm" onClick={handleAddTag}>
                Add
              </Button>
            </div>
          </div>
        </FormSection>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between p-4 border-t bg-muted/30">
        <p className="text-xs text-muted-foreground">
          This will create version {decision.version.version_number + 1}.
          The current version will be preserved.
        </p>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!isValid || amendMutation.isPending}
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
        <div className="absolute bottom-20 left-4 right-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
          <AlertCircle className="h-4 w-4 inline mr-2" />
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
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      {/* Modal */}
      <div className="relative w-full max-w-3xl max-h-[90vh] bg-background rounded-lg shadow-xl flex flex-col overflow-hidden">
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

function FormSection({ icon: Icon, title, description, children }: FormSectionProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 text-muted-foreground" />
        <h4 className="font-medium text-sm">{title}</h4>
      </div>
      {description && (
        <p className="text-xs text-muted-foreground">{description}</p>
      )}
      {children}
    </div>
  );
}

export default ProposeChangeModal;
