"use client";

import React, { useCallback, useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
  type Node,
  type Edge,
  type NodeTypes,
  type ConnectionMode,
  ReactFlowProvider,
  Panel,
} from "reactflow";
import "reactflow/dist/style.css";
import dagre from "@dagrejs/dagre";

export type LifecycleEvent = {
  id: string;
  type: string;
  ts: number;
  sandbox_id?: string | null;
  template_id?: string | null;
  preset?: string | null;
  label?: string | null;
};

const getLayoutedElements = (nodes: Node[], edges: Edge[], direction: "TB" | "LR" = "LR") => {
  const g = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction, ranksep: 80, nodesep: 50 });

  const nodeW = 56;
  const nodeH = 52;
  nodes.forEach((n) => g.setNode(n.id, { width: nodeW, height: nodeH }));
  edges.forEach((e) => g.setEdge(e.source, e.target));

  dagre.layout(g);

  return nodes.map((n) => {
    const pos = g.node(n.id);
    return {
      ...n,
      position: { x: pos.x - nodeW / 2, y: pos.y - nodeH / 2 },
    };
  });
};

function LifecycleNode({
  data,
}: {
  data: { event: LifecycleEvent; isActive?: boolean; nodeType: string };
}) {
  const { event, isActive, nodeType } = data;
  const preset = (event.preset ?? "sandbox").slice(0, 8);
  const shortId = event.sandbox_id?.slice(0, 5) ?? event.id.slice(0, 5);
  const tag = nodeType === "launch" ? `${preset} ${shortId}` : nodeType === "replay" ? `replay ${shortId}` : nodeType === "destroy" ? `× ${shortId}` : nodeType === "capture_stop" ? `saved ${shortId}` : `rec ${shortId}`;

  const ballClass =
    nodeType === "destroy"
      ? "bg-zinc-500 border border-zinc-400 shadow-inner"
      : nodeType === "replay"
        ? "bg-blue-500 border border-blue-400 shadow-[0_0_12px_rgba(59,130,246,0.5)]"
        : nodeType === "capture_start" || nodeType === "capture_stop"
          ? "bg-rose-500 border border-rose-400 shadow-[0_0_12px_rgba(244,63,94,0.4)]"
          : isActive
            ? "bg-[#3c9c66] border border-[#4caf50] shadow-[0_0_14px_rgba(60,156,102,0.5)] active-pulse"
            : "bg-[#3c9c66]/90 border border-[#3c9c66] shadow-[0_0_10px_rgba(60,156,102,0.3)]";

  return (
    <div className="group flex flex-col items-center gap-0.5">
      <Handle type="target" position={Position.Left} className="!w-2 !h-2 !border-2 !border-zinc-500 !bg-zinc-200" />
      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !border-2 !border-zinc-500 !bg-zinc-200" />
      <span className="text-[10px] font-medium text-muted-foreground whitespace-nowrap max-w-[72px] truncate font-mono" title={tag}>
        {tag}
      </span>
      <div
        className={`flex items-center justify-center rounded-full w-9 h-9 shrink-0 transition-transform group-hover:scale-105 ${ballClass} text-white font-bold`}
        title={tag}
      >
        {nodeType === "destroy" ? "×" : null}
      </div>
    </div>
  );
}

const nodeTypes: NodeTypes = {
  lifecycle: LifecycleNode,
};

function buildGraph(
  events: LifecycleEvent[],
  activeSandboxIds: Set<string>
): { nodes: Node[]; edges: Edge[] } {
  const sorted = [...events].sort((a, b) => a.ts - b.ts);
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const launchBySandbox = new Map<string, string>();
  const captureStartBySandbox: { sandbox_id: string; id: string; ts: number }[] = [];
  const captureStopByTemplate = new Map<string, string>();

  const edgeStyle = { stroke: "#52525b", strokeWidth: 2 };
  const edgeLabelProps = {
    labelShowBg: true,
    labelStyle: { fontSize: 10, fill: "#a1a1aa" },
    labelBgStyle: { fill: "#18181b", stroke: "#27272a" },
    labelBgPadding: [4, 2] as [number, number],
    labelBgBorderRadius: 4,
  };

  sorted.forEach((ev, idx) => {
    const nodeType =
      ev.type === "destroy"
        ? "destroy"
        : ev.type === "launch" && ev.template_id
          ? "replay"
          : ev.type === "capture_start"
            ? "capture_start"
            : ev.type === "capture_stop"
              ? "capture_stop"
              : "launch";

    nodes.push({
      id: ev.id,
      type: "lifecycle",
      position: { x: 0, y: 0 },
      data: {
        event: ev,
        isActive: ev.sandbox_id ? activeSandboxIds.has(ev.sandbox_id) : false,
        nodeType,
      },
    });

    if (ev.type === "launch" && ev.sandbox_id) {
      launchBySandbox.set(ev.sandbox_id, ev.id);
    }
    if (ev.type === "capture_start" && ev.sandbox_id) {
      captureStartBySandbox.push({ sandbox_id: ev.sandbox_id, id: ev.id, ts: ev.ts });
    }
    if (ev.type === "capture_stop" && ev.template_id) {
      captureStopByTemplate.set(ev.template_id, ev.id);
    }
    if (ev.type === "destroy" && ev.sandbox_id) {
    const launchId = launchBySandbox.get(ev.sandbox_id);
    if (launchId)
      edges.push({
        id: `e-launch-destroy-${ev.id}`,
        source: launchId,
        target: ev.id,
        type: "smoothstep",
        style: edgeStyle,
        label: "destroyed",
        ...edgeLabelProps,
      });
  }
  });

  // launch -> capture_start (same sandbox_id; time order: launch first)
  captureStartBySandbox.forEach(({ sandbox_id, id: capId }) => {
    const launchId = launchBySandbox.get(sandbox_id);
    if (launchId)
      edges.push({
        id: `e-launch-cs-${capId}`,
        source: launchId,
        target: capId,
        type: "smoothstep",
        style: edgeStyle,
        label: "recorded",
        ...edgeLabelProps,
      });
  });

  // capture_start -> capture_stop (same sandbox, most recent start before this stop)
  sorted.forEach((ev) => {
    if (ev.type !== "capture_stop" || !ev.sandbox_id) return;
    const before = captureStartBySandbox.filter((c) => c.sandbox_id === ev.sandbox_id && c.ts <= ev.ts);
    const latest = before.sort((a, b) => b.ts - a.ts)[0];
    if (latest)
      edges.push({
        id: `e-cs-cp-${ev.id}`,
        source: latest.id,
        target: ev.id,
        type: "smoothstep",
        style: edgeStyle,
        label: "saved",
        ...edgeLabelProps,
      });
  });

  // capture_stop -> replay (template saved then replayed; edge from template to replay launch)
  sorted.forEach((ev) => {
    if (ev.type !== "launch" || !ev.template_id) return;
    const stopId = captureStopByTemplate.get(ev.template_id);
    if (stopId)
      edges.push({
        id: `e-tpl-replay-${ev.id}`,
        source: stopId,
        target: ev.id,
        type: "smoothstep",
        style: edgeStyle,
        label: "replayed",
        ...edgeLabelProps,
      });
  });

  return { nodes, edges };
}

function LifecycleGraphInner({
  events,
  activeSandboxIds,
}: {
  events: LifecycleEvent[];
  activeSandboxIds: Set<string>;
}) {
  const { nodes: initialNodes, edges: initialEdges } = useMemo(
    () => buildGraph(events, activeSandboxIds),
    [events, activeSandboxIds]
  );
  const layouted = useMemo(
    () => getLayoutedElements(initialNodes, initialEdges, "LR"),
    [initialNodes, initialEdges]
  );
  const [nodes, setNodes, onNodesChange] = useNodesState(layouted);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  React.useEffect(() => {
    const { nodes: n, edges: e } = buildGraph(events, activeSandboxIds);
    const laid = getLayoutedElements(n, e, "LR");
    setNodes(laid);
    setEdges(e);
  }, [events, activeSandboxIds, setNodes, setEdges]);

  return (
    <div className="lifecycle-graph h-[420px] w-full rounded-xl border border-[#363636] bg-card">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        defaultEdgeOptions={{ type: "smoothstep", style: { stroke: "#52525b", strokeWidth: 2 } }}
        connectionMode={"loose" as ConnectionMode}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={12} size={1} color="#27272a" />
        <Controls showInteractive={false} />
        <MiniMap nodeColor={(n) => (n.data?.nodeType === "destroy" ? "#a8a29e" : n.data?.nodeType === "replay" ? "#0ea5e9" : n.data?.nodeType === "capture_start" || n.data?.nodeType === "capture_stop" ? "#e11d48" : "#059669")} />
        <Panel position="top-left" className="text-xs font-medium text-muted-foreground font-sans">
          Lifecycle · {events.length} events
        </Panel>
      </ReactFlow>
    </div>
  );
}

export default function LifecycleGraph({
  events,
  activeSandboxIds,
}: {
  events: LifecycleEvent[];
  activeSandboxIds: Set<string>;
}) {
  return (
    <ReactFlowProvider>
      <LifecycleGraphInner events={events} activeSandboxIds={activeSandboxIds} />
    </ReactFlowProvider>
  );
}
