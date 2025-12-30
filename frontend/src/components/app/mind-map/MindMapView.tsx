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
  MarkerType,
  Panel,
  ConnectionMode,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { DecisionNode, type DecisionNodeData } from "./DecisionNode";
import { Button } from "@/components/ui/button";
import { Sparkles, Loader2, Plus, Trash2 } from "lucide-react";
import { useApiClient } from "@/hooks/use-api";
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
  influenced_by: "#8b5cf6", // purple
  led_to: "#10b981", // green
  related_to: "#6b7280", // gray
  supersedes: "#ef4444", // red
  conflicts_with: "#f59e0b", // amber
  blocked_by: "#dc2626", // dark red
  implements: "#3b82f6", // blue
};

const edgeLabels: Record<RelationshipType, string> = {
  influenced_by: "influenced by",
  led_to: "led to",
  related_to: "related to",
  supersedes: "supersedes",
  conflicts_with: "conflicts with",
  blocked_by: "blocked by",
  implements: "implements",
};

interface MindMapViewProps {
  decisions: DecisionSummary[];
  onAddRelationship?: () => void;
}

export function MindMapView({
  decisions,
  onAddRelationship,
}: MindMapViewProps) {
  const client = useApiClient();
  const [nodes, setNodes, onNodesChange] = useNodesState<DecisionNodeType>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [relationships, setRelationships] = useState<MindMapRelationship[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);

  // Limit to 8 most recent decisions
  const limitedDecisions = useMemo(() => {
    return decisions.slice(0, 8);
  }, [decisions]);

  // Fetch existing relationships
  const fetchRelationships = useCallback(async () => {
    if (limitedDecisions.length === 0) {
      setIsLoading(false);
      return;
    }

    try {
      const ids = limitedDecisions.map((d) => d.id).join(",");
      const response = await client.get(
        `/decisions/relationships?decision_ids=${ids}`,
      );
      setRelationships(response.data.relationships || []);
    } catch (error) {
      console.error("Failed to fetch relationships:", error);
    } finally {
      setIsLoading(false);
    }
  }, [client, limitedDecisions]);

  useEffect(() => {
    fetchRelationships();
  }, [fetchRelationships]);

  // Calculate node positions in a circular/grid layout
  const calculateNodePositions = useCallback((count: number) => {
    const positions: { x: number; y: number }[] = [];
    const centerX = 400;
    const centerY = 300;

    if (count <= 4) {
      // 2x2 grid
      const gridPositions = [
        { x: centerX - 150, y: centerY - 120 },
        { x: centerX + 150, y: centerY - 120 },
        { x: centerX - 150, y: centerY + 120 },
        { x: centerX + 150, y: centerY + 120 },
      ];
      return gridPositions.slice(0, count);
    } else if (count <= 6) {
      // 3x2 grid
      const gridPositions = [
        { x: centerX - 250, y: centerY - 120 },
        { x: centerX, y: centerY - 120 },
        { x: centerX + 250, y: centerY - 120 },
        { x: centerX - 250, y: centerY + 120 },
        { x: centerX, y: centerY + 120 },
        { x: centerX + 250, y: centerY + 120 },
      ];
      return gridPositions.slice(0, count);
    } else {
      // Circular layout for 7-8 nodes
      const radius = 280;
      for (let i = 0; i < count; i++) {
        const angle = (i * 2 * Math.PI) / count - Math.PI / 2;
        positions.push({
          x: centerX + radius * Math.cos(angle),
          y: centerY + radius * Math.sin(angle),
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
  const handleGenerateRelationships = async () => {
    setIsGenerating(true);
    try {
      const decisionIds = limitedDecisions.map((d) => d.id);
      const response = await client.post("/decisions/relationships", {
        action: "generate",
        decision_ids: decisionIds,
      });

      if (response.data.relationships?.length > 0) {
        // Refresh relationships
        await fetchRelationships();
      }
    } catch (error) {
      console.error("Failed to generate relationships:", error);
    } finally {
      setIsGenerating(false);
    }
  };

  // Delete selected relationship
  const handleDeleteRelationship = async () => {
    if (!selectedEdge) return;

    try {
      await client.delete(`/decisions/relationships/${selectedEdge}`);
      setRelationships((prev) => prev.filter((r) => r.id !== selectedEdge));
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
    </div>
  );
}
