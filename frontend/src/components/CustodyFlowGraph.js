/**
 * Custody Flow Graph Component v2.1
 * Visual tree diagram showing how assets flow through wallets
 * Uses React Flow for interactive node-based visualization
 * Last updated: Mar 10, 2026 - Mobile responsive
 */
import React, { useMemo, useCallback } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';

// Custom node component for wallet addresses
const WalletNode = ({ data }) => {
  const getBgColor = () => {
    switch (data.type) {
      case 'exchange': return 'bg-green-900 border-green-500';
      case 'dex': return 'bg-blue-900 border-blue-500';
      case 'dormant': return 'bg-orange-900 border-orange-500';
      case 'target': return 'bg-purple-900 border-purple-500';
      default: return 'bg-slate-800 border-slate-600';
    }
  };

  const getIcon = () => {
    switch (data.type) {
      case 'exchange': return '🏦';
      case 'dex': return '🔄';
      case 'dormant': return '💤';
      case 'target': return '🎯';
      default: return '👛';
    }
  };

  return (
    <div className={`px-4 py-3 rounded-lg border-2 ${getBgColor()} min-w-[180px] shadow-lg`}>
      <div className="flex items-center gap-2 mb-1">
        <span className="text-lg">{getIcon()}</span>
        <span className="text-xs font-semibold text-white uppercase tracking-wide">
          {data.label || data.type}
        </span>
      </div>
      <div className="text-xs font-mono text-gray-300 truncate" title={data.address}>
        {data.address ? `${data.address.slice(0, 8)}...${data.address.slice(-6)}` : ''}
      </div>
      {data.value && (
        <div className="text-sm font-bold text-white mt-1">
          {data.value.toFixed(4)} {data.asset || 'ETH'}
        </div>
      )}
      {data.exchangeName && (
        <div className="text-xs text-green-300 mt-1 font-semibold">
          {data.exchangeName}
        </div>
      )}
      {data.dexName && (
        <div className="text-xs text-blue-300 mt-1 font-semibold">
          {data.dexName}
        </div>
      )}
    </div>
  );
};

const nodeTypes = {
  wallet: WalletNode,
};

export const CustodyFlowGraph = ({ result, chain }) => {
  // Convert custody chain data to React Flow nodes and edges
  const { nodes: initialNodes, edges: initialEdges } = useMemo(() => {
    if (!result || !result.custody_chain || result.custody_chain.length === 0) {
      return { nodes: [], edges: [] };
    }

    const nodesMap = new Map();
    const edges = [];
    
    // Add the target address as the root node
    const targetAddress = result.analyzed_address;
    nodesMap.set(targetAddress, {
      id: targetAddress,
      type: 'wallet',
      position: { x: 400, y: 50 },
      data: {
        address: targetAddress,
        type: 'target',
        label: 'Analyzed Wallet'
      }
    });

    // Process custody chain to create nodes and edges
    let yOffset = 150;
    const levelMap = new Map(); // Track nodes at each depth level
    
    result.custody_chain.forEach((link, index) => {
      const fromAddr = link.from;
      const toAddr = link.to;
      const depth = link.depth || 1;
      
      // Initialize level tracking
      if (!levelMap.has(depth)) {
        levelMap.set(depth, []);
      }
      
      // Add source node if not exists
      if (!nodesMap.has(fromAddr)) {
        const levelNodes = levelMap.get(depth);
        const xOffset = 100 + (levelNodes.length * 250);
        
        let nodeType = 'transfer';
        let label = 'Wallet';
        let exchangeName = null;
        let dexName = null;
        
        if (link.origin_type === 'exchange') {
          nodeType = 'exchange';
          label = 'Exchange';
          exchangeName = link.exchange_name;
        } else if (link.origin_type === 'dex_swap') {
          nodeType = 'dex';
          label = 'DEX';
          dexName = link.dex_name;
        } else if (link.origin_type === 'dormant') {
          nodeType = 'dormant';
          label = 'Dormant';
        }
        
        nodesMap.set(fromAddr, {
          id: fromAddr,
          type: 'wallet',
          position: { x: xOffset, y: yOffset + (depth * 120) },
          data: {
            address: fromAddr,
            type: nodeType,
            label: label,
            value: link.value,
            asset: link.asset,
            exchangeName,
            dexName
          }
        });
        
        levelNodes.push(fromAddr);
      }
      
      // Create edge
      const edgeId = `${fromAddr}-${toAddr}-${index}`;
      edges.push({
        id: edgeId,
        source: fromAddr,
        target: toAddr,
        type: 'smoothstep',
        animated: link.origin_type === 'exchange' || link.origin_type === 'dex_swap',
        style: { 
          stroke: link.origin_type === 'exchange' ? '#22c55e' : 
                  link.origin_type === 'dex_swap' ? '#3b82f6' :
                  link.origin_type === 'dormant' ? '#f97316' : '#6b7280',
          strokeWidth: 2
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: link.origin_type === 'exchange' ? '#22c55e' : 
                 link.origin_type === 'dex_swap' ? '#3b82f6' :
                 link.origin_type === 'dormant' ? '#f97316' : '#6b7280',
        },
        label: link.value ? `${link.value.toFixed(4)} ${link.asset || 'ETH'}` : '',
        labelStyle: { fill: '#9ca3af', fontSize: 10 },
        labelBgStyle: { fill: '#1e293b', fillOpacity: 0.8 }
      });
    });

    return {
      nodes: Array.from(nodesMap.values()),
      edges
    };
  }, [result]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Custom minimap node color
  const nodeColor = useCallback((node) => {
    switch (node.data?.type) {
      case 'exchange': return '#22c55e';
      case 'dex': return '#3b82f6';
      case 'dormant': return '#f97316';
      case 'target': return '#a855f7';
      default: return '#475569';
    }
  }, []);

  if (!result || !result.custody_chain || result.custody_chain.length === 0) {
    return (
      <div className="h-[500px] flex items-center justify-center bg-slate-900/50 rounded-lg border border-slate-700">
        <div className="text-center text-gray-400">
          <p className="text-lg mb-2">No custody data to visualize</p>
          <p className="text-sm">Run an analysis to see the flow graph</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[500px] bg-slate-900 rounded-lg border border-slate-700 overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.1}
        maxZoom={2}
        defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
      >
        <Background color="#334155" gap={20} size={1} />
        <Controls 
          className="bg-slate-800 border-slate-600 rounded-lg"
          showInteractive={false}
        />
        <MiniMap 
          nodeColor={nodeColor}
          maskColor="rgba(15, 23, 42, 0.8)"
          className="bg-slate-800 border-slate-600 rounded-lg"
        />
      </ReactFlow>
      
      {/* Legend */}
      <div className="absolute bottom-4 left-4 bg-slate-800/90 p-3 rounded-lg border border-slate-700 text-xs">
        <div className="font-semibold text-white mb-2">Legend</div>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-purple-500"></div>
            <span className="text-gray-300">Target Wallet</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-green-500"></div>
            <span className="text-gray-300">Exchange Origin</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-blue-500"></div>
            <span className="text-gray-300">DEX Swap</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-orange-500"></div>
            <span className="text-gray-300">Dormant Wallet</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-slate-500"></div>
            <span className="text-gray-300">Transfer</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CustodyFlowGraph;
