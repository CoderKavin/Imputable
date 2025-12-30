"use client";

import { useState } from "react";
import { X, ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useApiClient } from "@/hooks/use-api";
import type { DecisionSummary, RelationshipType } from "@/types/decision";

interface AddRelationshipModalProps {
  decisions: DecisionSummary[];
  onClose: () => void;
  onSuccess?: () => void;
}

const relationshipTypes: {
  value: RelationshipType;
  label: string;
  description: string;
}[] = [
  {
    value: "supersedes",
    label: "Supersedes",
    description: "This decision replaces another",
  },
  {
    value: "blocked_by",
    label: "Blocked by",
    description: "This decision is blocked by another",
  },
  {
    value: "related_to",
    label: "Related to",
    description: "Decisions share common themes",
  },
  {
    value: "implements",
    label: "Implements",
    description: "This decision implements another",
  },
  {
    value: "conflicts_with",
    label: "Conflicts with",
    description: "Decisions are in tension",
  },
];

export function AddRelationshipModal({
  decisions,
  onClose,
  onSuccess,
}: AddRelationshipModalProps) {
  const client = useApiClient();
  const [sourceId, setSourceId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [relationshipType, setRelationshipType] =
    useState<RelationshipType>("related_to");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!sourceId || !targetId) {
      setError("Please select both decisions");
      return;
    }

    if (sourceId === targetId) {
      setError("Cannot create a relationship between the same decision");
      return;
    }

    setIsSubmitting(true);
    try {
      await client.post("/decisions/relationships", {
        source_decision_id: sourceId,
        target_decision_id: targetId,
        relationship_type: relationshipType,
        description: description.trim() || undefined,
      });
      onSuccess?.();
      onClose();
    } catch (err: any) {
      if (err.response?.status === 409) {
        setError("This relationship already exists");
      } else {
        setError(err.response?.data?.error || "Failed to create relationship");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative z-[201] bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">
            Add Relationship
          </h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Source Decision */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              From Decision
            </label>
            <select
              value={sourceId}
              onChange={(e) => setSourceId(e.target.value)}
              className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            >
              <option value="">Select a decision...</option>
              {decisions.map((d) => (
                <option key={d.id} value={d.id}>
                  DECISION-{d.decision_number}: {d.title.substring(0, 50)}
                  {d.title.length > 50 ? "..." : ""}
                </option>
              ))}
            </select>
          </div>

          {/* Relationship Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Relationship Type
            </label>
            <div className="flex items-center gap-2 mb-3">
              <div className="flex-1 h-px bg-gray-200" />
              <ArrowRight className="w-5 h-5 text-indigo-500" />
              <div className="flex-1 h-px bg-gray-200" />
            </div>
            <select
              value={relationshipType}
              onChange={(e) =>
                setRelationshipType(e.target.value as RelationshipType)
              }
              className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            >
              {relationshipTypes.map((rt) => (
                <option key={rt.value} value={rt.value}>
                  {rt.label}
                </option>
              ))}
            </select>
            <p className="mt-1.5 text-xs text-gray-500">
              {
                relationshipTypes.find((rt) => rt.value === relationshipType)
                  ?.description
              }
            </p>
          </div>

          {/* Target Decision */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              To Decision
            </label>
            <select
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
              className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            >
              <option value="">Select a decision...</option>
              {decisions.map((d) => (
                <option key={d.id} value={d.id}>
                  DECISION-{d.decision_number}: {d.title.substring(0, 50)}
                  {d.title.length > 50 ? "..." : ""}
                </option>
              ))}
            </select>
          </div>

          {/* Description (optional) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Description{" "}
              <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Why are these decisions related?"
              rows={2}
              className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
            />
          </div>

          {/* Error */}
          {error && (
            <div className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              className="flex-1 rounded-xl"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting || !sourceId || !targetId}
              className="flex-1 rounded-xl"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Creating...
                </>
              ) : (
                "Create Relationship"
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
