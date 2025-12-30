"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeTypes,
  type Connection,
  MarkerType,
  Panel,
  ConnectionMode,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { DecisionNode, type DecisionNodeData } from "./DecisionNode";
import { Button } from "@/components/ui/button";
import { Sparkles, Loader2, Plus, Trash2 } from "lucide-react";
import { useApiClient } from "@/hooks/use-api";
import { useDecisionRelationships } from "@/hooks/use-decisions";
import { useQueryClient } from "@tanstack/react-query";
import type {
  DecisionSummary,
  MindMapRelationship,
  RelationshipType,
} from "@/types/decision";

// Define the custom node type
type DecisionNodeType = Node<DecisionNodeData, "decision">;

const nodeTypes: NodeTypes = {
  decision: DecisionNode,
};

// Edge colors based on relationship type
const edgeColors: Record<RelationshipType, string> = {
  supersedes: "#ef4444", // red
  blocked_by: "#dc2626", // dark red
  related_to: "#6b7280", // gray
  implements: "#3b82f6", // blue
  conflicts_with: "#f59e0b", // amber
};

const edgeLabels: Record<RelationshipType, string> = {
  supersedes: "supersedes",
  blocked_by: "blocked by",
  related_to: "related to",
  implements: "implements",
  conflicts_with: "conflicts with",
};

interface MindMapViewProps {
  decisions: DecisionSummary[];
  maxDecisions?: number;
  onAddRelationship?: () => void;
}

export function MindMapView({
  decisions,
  maxDecisions = 8,
  onAddRelationship,
}: MindMapViewProps) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const [nodes, setNodes, onNodesChange] = useNodesState<DecisionNodeType>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);
  const [pendingConnection, setPendingConnection] = useState<{
    source: string;
    target: string;
  } | null>(null);
  const [isCreatingConnection, setIsCreatingConnection] = useState(false);

  // Limit to maxDecisions most recent decisions (sorted by created_at descending)
  const limitedDecisions = useMemo(() => {
    const sorted = [...decisions].sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
    return sorted.slice(0, maxDecisions);
  }, [decisions, maxDecisions]);

  // Use React Query hook for relationships - cached and instant on subsequent loads
  const decisionIds = useMemo(
    () => limitedDecisions.map((d) => d.id),
    [limitedDecisions],
  );
  const { data: relationshipsData, isLoading } =
    useDecisionRelationships(decisionIds);
  const relationships = relationshipsData?.relationships || [];

  // Invalidate relationships cache to refetch
  const refreshRelationships = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["relationships"] });
  }, [queryClient]);

  // Calculate node positions in a circular/grid layout
  const calculateNodePositions = useCallback((count: number) => {
    const positions: { x: number; y: number }[] = [];
    const centerX = 500;
    const centerY = 350;

    if (count <= 4) {
      // 2x2 grid
      const gridPositions = [
        { x: centerX - 180, y: centerY - 140 },
        { x: centerX + 180, y: centerY - 140 },
        { x: centerX - 180, y: centerY + 140 },
        { x: centerX + 180, y: centerY + 140 },
      ];
      return gridPositions.slice(0, count);
    } else if (count <= 6) {
      // 3x2 grid
      const gridPositions = [
        { x: centerX - 280, y: centerY - 140 },
        { x: centerX, y: centerY - 140 },
        { x: centerX + 280, y: centerY - 140 },
        { x: centerX - 280, y: centerY + 140 },
        { x: centerX, y: centerY + 140 },
        { x: centerX + 280, y: centerY + 140 },
      ];
      return gridPositions.slice(0, count);
    } else if (count <= 8) {
      // Circular layout for 7-8 nodes
      const radius = 300;
      for (let i = 0; i < count; i++) {
        const angle = (i * 2 * Math.PI) / count - Math.PI / 2;
        positions.push({
          x: centerX + radius * Math.cos(angle),
          y: centerY + radius * Math.sin(angle),
        });
      }
      return positions;
    } else if (count <= 12) {
      // Dual ring layout for 9-12 nodes
      const innerRadius = 200;
      const outerRadius = 380;
      const innerCount = Math.min(4, count);
      const outerCount = count - innerCount;

      // Inner ring
      for (let i = 0; i < innerCount; i++) {
        const angle = (i * 2 * Math.PI) / innerCount - Math.PI / 2;
        positions.push({
          x: centerX + innerRadius * Math.cos(angle),
          y: centerY + innerRadius * Math.sin(angle),
        });
      }

      // Outer ring
      for (let i = 0; i < outerCount; i++) {
        const angle =
          (i * 2 * Math.PI) / outerCount - Math.PI / 2 + Math.PI / outerCount;
        positions.push({
          x: centerX + outerRadius * Math.cos(angle),
          y: centerY + outerRadius * Math.sin(angle),
        });
      }
      return positions;
    } else {
      // Large grid layout for 13+ nodes (4 columns)
      const cols = 4;
      const spacing = { x: 280, y: 180 };
      const startX = centerX - ((cols - 1) * spacing.x) / 2;
      const rows = Math.ceil(count / cols);
      const startY = centerY - ((rows - 1) * spacing.y) / 2;

      for (let i = 0; i < count; i++) {
        const row = Math.floor(i / cols);
        const col = i % cols;
        positions.push({
          x: startX + col * spacing.x,
          y: startY + row * spacing.y,
        });
      }
      return positions;
    }
  }, []);

  // Build nodes from decisions
  useEffect(() => {
    const positions = calculateNodePositions(limitedDecisions.length);

    const newNodes: DecisionNodeType[] = limitedDecisions.map(
      (decision, index) => ({
        id: decision.id,
        type: "decision" as const,
        position: positions[index] || { x: 0, y: 0 },
        data: {
          decision_number: decision.decision_number,
          title: decision.title,
          status: decision.status,
          impact_level: decision.impact_level,
          created_at: decision.created_at,
        },
      }),
    );

    setNodes(newNodes);
  }, [limitedDecisions, calculateNodePositions, setNodes]);

  // Build edges from relationships
  useEffect(() => {
    const decisionIds = new Set(limitedDecisions.map((d) => d.id));

    const newEdges: Edge[] = relationships
      .filter(
        (rel) =>
          decisionIds.has(rel.source_decision_id) &&
          decisionIds.has(rel.target_decision_id),
      )
      .map((rel) => ({
        id: rel.id,
        source: rel.source_decision_id,
        target: rel.target_decision_id,
        type: "smoothstep",
        animated:
          rel.relationship_type === "conflicts_with" ||
          rel.relationship_type === "blocked_by",
        label: edgeLabels[rel.relationship_type],
        labelStyle: {
          fontSize: 10,
          fontWeight: 500,
          fill: edgeColors[rel.relationship_type],
        },
        labelBgStyle: {
          fill: "white",
          fillOpacity: 0.9,
        },
        labelBgPadding: [4, 2] as [number, number],
        labelBgBorderRadius: 4,
        style: {
          stroke: edgeColors[rel.relationship_type],
          strokeWidth: selectedEdge === rel.id ? 3 : 2,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: edgeColors[rel.relationship_type],
          width: 20,
          height: 20,
        },
        data: {
          relationship: rel,
        },
      }));

    setEdges(newEdges);
  }, [relationships, limitedDecisions, setEdges, selectedEdge]);

  // Generate AI relationships
  const [aiMessage, setAiMessage] = useState<{
    type: "success" | "info" | "error";
    text: string;
  } | null>(null);

  const handleGenerateRelationships = async () => {
    setIsGenerating(true);
    setAiMessage(null);
    try {
      const decisionIds = limitedDecisions.map((d) => d.id);
      const response = await client.post("/decisions/relationships", {
        action: "generate",
        decision_ids: decisionIds,
      });

      const newRelationships = response.data.relationships || [];

      if (newRelationships.length > 0) {
        refreshRelationships();
        setAiMessage({
          type: "success",
          text: `Found ${newRelationships.length} new connection${newRelationships.length > 1 ? "s" : ""}!`,
        });
      } else {
        setAiMessage({
          type: "info",
          text: "No new connections found. Try adding more decisions with detailed context.",
        });
      }

      // Auto-hide message after 5 seconds
      setTimeout(() => setAiMessage(null), 5000);
    } catch (error: any) {
      console.error("Failed to generate relationships:", error);
      setAiMessage({
        type: "error",
        text:
          error.response?.data?.error ||
          "Failed to analyze decisions. Please try again.",
      });
      setTimeout(() => setAiMessage(null), 5000);
    } finally {
      setIsGenerating(false);
    }
  };

  // Delete selected relationship
  const handleDeleteRelationship = async () => {
    if (!selectedEdge) return;

    try {
      await client.delete(`/decisions/relationships/${selectedEdge}`);
      refreshRelationships();
      setSelectedEdge(null);
    } catch (error) {
      console.error("Failed to delete relationship:", error);
    }
  };

  // Handle edge click for selection
  const onEdgeClick = useCallback((_: React.MouseEvent, edge: Edge) => {
    setSelectedEdge((prev) => (prev === edge.id ? null : edge.id));
  }, []);

  // Handle background click to deselect
  const onPaneClick = useCallback(() => {
    setSelectedEdge(null);
  }, []);

  // Handle drag-to-connect
  const onConnect = useCallback((connection: Connection) => {
    if (
      connection.source &&
      connection.target &&
      connection.source !== connection.target
    ) {
      setPendingConnection({
        source: connection.source,
        target: connection.target,
      });
    }
  }, []);

  // Create connection with selected relationship type
  const handleCreateConnection = async (relationshipType: RelationshipType) => {
    if (!pendingConnection) return;

    setIsCreatingConnection(true);
    try {
      const response = await client.post("/decisions/relationships", {
        source_decision_id: pendingConnection.source,
        target_decision_id: pendingConnection.target,
        relationship_type: relationshipType,
      });
      console.log("Relationship created:", response.data);
      refreshRelationships();
    } catch (error: any) {
      console.error("Failed to create relationship:", error);
      if (error.response?.status === 409) {
        alert("This relationship already exists");
      } else {
        alert(
          error.response?.data?.error ||
            "Failed to create relationship. Please try again.",
        );
      }
    } finally {
      setIsCreatingConnection(false);
      setPendingConnection(null);
    }
  };

  if (isLoading) {
    return (
      <div className="h-[600px] flex items-center justify-center bg-gray-50 rounded-2xl border border-gray-200">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
          <span className="text-gray-500">Loading mind map...</span>
        </div>
      </div>
    );
  }

  if (limitedDecisions.length === 0) {
    return (
      <div className="h-[600px] flex items-center justify-center bg-gray-50 rounded-2xl border border-gray-200">
        <div className="text-center">
          <div className="w-16 h-16 rounded-2xl bg-gray-100 flex items-center justify-center mx-auto mb-4">
            <Sparkles className="w-8 h-8 text-gray-400" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            No decisions yet
          </h3>
          <p className="text-gray-500 max-w-sm">
            Create some decisions to see them visualized as a mind map.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[600px] rounded-2xl border border-gray-200 overflow-hidden bg-white shadow-sm">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onEdgeClick={onEdgeClick}
        onPaneClick={onPaneClick}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        connectionMode={ConnectionMode.Loose}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        minZoom={0.3}
        maxZoom={1.5}
        defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#e5e7eb" gap={20} size={1} />

        <Controls
          showInteractive={false}
          className="!bg-white !border !border-gray-200 !rounded-xl !shadow-sm"
        />

        <MiniMap
          nodeColor={(node) => {
            const data = node.data as DecisionNodeData;
            switch (data?.status) {
              case "approved":
                return "#10b981";
              case "pending_review":
                return "#f59e0b";
              case "deprecated":
                return "#ef4444";
              case "superseded":
                return "#64748b";
              default:
                return "#9ca3af";
            }
          }}
          maskColor="rgba(255, 255, 255, 0.8)"
          className="!bg-white !border !border-gray-200 !rounded-xl"
        />

        {/* Top panel with actions */}
        <Panel position="top-right" className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={handleGenerateRelationships}
            disabled={isGenerating || limitedDecisions.length < 2}
            className="rounded-xl bg-white shadow-sm"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Analyzing...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 mr-2" />
                AI Discover Links
              </>
            )}
          </Button>

          {onAddRelationship && (
            <Button
              size="sm"
              variant="outline"
              onClick={onAddRelationship}
              className="rounded-xl bg-white shadow-sm"
            >
              <Plus className="w-4 h-4 mr-2" />
              Add Link
            </Button>
          )}

          {selectedEdge && (
            <Button
              size="sm"
              variant="outline"
              onClick={handleDeleteRelationship}
              className="rounded-xl bg-white shadow-sm text-red-600 hover:text-red-700 hover:bg-red-50"
            >
              <Trash2 className="w-4 h-4 mr-2" />
              Delete Link
            </Button>
          )}
        </Panel>

        {/* AI Message Toast */}
        {aiMessage && (
          <Panel position="top-center" className="pointer-events-none">
            <div
              className={`
                px-4 py-2.5 rounded-xl shadow-lg text-sm font-medium pointer-events-auto
                ${aiMessage.type === "success" ? "bg-emerald-500 text-white" : ""}
                ${aiMessage.type === "info" ? "bg-amber-500 text-white" : ""}
                ${aiMessage.type === "error" ? "bg-red-500 text-white" : ""}
              `}
            >
              {aiMessage.text}
            </div>
          </Panel>
        )}

        {/* Legend */}
        <Panel
          position="bottom-left"
          className="bg-white/90 backdrop-blur-sm rounded-xl border border-gray-200 p-3 shadow-sm"
        >
          <div className="text-xs font-medium text-gray-700 mb-2">
            Relationship Types
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            {Object.entries(edgeLabels).map(([type, label]) => (
              <div key={type} className="flex items-center gap-2">
                <div
                  className="w-3 h-0.5 rounded-full"
                  style={{
                    backgroundColor: edgeColors[type as RelationshipType],
                  }}
                />
                <span className="text-[10px] text-gray-600 capitalize">
                  {label}
                </span>
              </div>
            ))}
          </div>
        </Panel>

        {/* Info panel */}
        <Panel
          position="top-left"
          className="bg-white/90 backdrop-blur-sm rounded-xl border border-gray-200 px-3 py-2 shadow-sm"
        >
          <div className="text-xs text-gray-500">
            Showing{" "}
            <span className="font-semibold text-gray-700">
              {limitedDecisions.length}
            </span>{" "}
            decisions
            {relationships.length > 0 && (
              <>
                {" "}
                with{" "}
                <span className="font-semibold text-gray-700">
                  {relationships.length}
                </span>{" "}
                connections
              </>
            )}
          </div>
        </Panel>
      </ReactFlow>

      {/* Relationship Type Picker Modal */}
      {pendingConnection && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => setPendingConnection(null)}
          />
          <div className="relative z-[201] bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h3 className="text-base font-semibold text-gray-900">
                Select Relationship Type
              </h3>
              <p className="text-xs text-gray-500 mt-1">
                How are these decisions related?
              </p>
            </div>
            <div className="p-3 space-y-1 max-h-[300px] overflow-y-auto">
              {(Object.entries(edgeLabels) as [RelationshipType, string][]).map(
                ([type, label]) => (
                  <button
                    key={type}
                    onClick={() => handleCreateConnection(type)}
                    disabled={isCreatingConnection}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-gray-50 transition-colors text-left disabled:opacity-50"
                  >
                    <div
                      className="w-4 h-1 rounded-full"
                      style={{ backgroundColor: edgeColors[type] }}
                    />
                    <span className="text-sm font-medium text-gray-700 capitalize">
                      {label}
                    </span>
                  </button>
                ),
              )}
            </div>
            <div className="px-5 py-3 border-t border-gray-100 bg-gray-50">
              <button
                onClick={() => setPendingConnection(null)}
                className="w-full text-sm text-gray-600 hover:text-gray-800 font-medium"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
