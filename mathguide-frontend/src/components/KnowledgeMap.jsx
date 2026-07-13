import { useState, useEffect } from 'react';
import { getStageMap } from '../api/mathguide';
import './KnowledgeMap.css';

const NODE_R = 18;
const LAYER_GAP = 70;
const NODE_GAP = 28;

export default function KnowledgeMap({ userId, onNodeClick }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!userId) return;
    setLoading(true);
    getStageMap(userId)
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [userId]);

  if (loading) return <div className="km-loading">加载地图...</div>;
  if (error) return <div className="km-error">{error}</div>;
  if (!data?.layers) return null;

  const { layers, prerequisites } = data;

  // Calculate positions
  const nodePos = {};
  let maxWidth = 0;
  layers.forEach((layer, li) => {
    const nodes = layer.nodes || [];
    const totalHeight = nodes.length * (NODE_R * 2 + NODE_GAP) - NODE_GAP;
    nodes.forEach((node, ni) => {
      nodePos[node.node_id] = {
        x: li * LAYER_GAP + NODE_R + 10,
        y: ni * (NODE_R * 2 + NODE_GAP) + NODE_R + 10,
      };
    });
    if (totalHeight > maxWidth) maxWidth = totalHeight;
  });

  const svgW = layers.length * LAYER_GAP + 20;
  const svgH = maxWidth + 20;

  function getColor(node) {
    if (node.status === 'cleared') return '#10b981';
    if (node.status === 'unlocked') return '#f59e0b';
    return '#d1d5db';
  }

  return (
    <div className="km-container">
      <svg width={svgW} height={Math.max(svgH, 200)} viewBox={`0 0 ${svgW} ${Math.max(svgH, 200)}`}>
        <defs>
          <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#9ca3af" />
          </marker>
        </defs>

        {/* Edges */}
        {(prerequisites || []).map((edge, i) => {
          const from = nodePos[edge.from];
          const to = nodePos[edge.to];
          if (!from || !to) return null;
          return (
            <line
              key={i}
              x1={from.x}
              y1={from.y}
              x2={to.x}
              y2={to.y}
              stroke="#d1d5db"
              strokeWidth={1.5}
              markerEnd="url(#arrowhead)"
            />
          );
        })}

        {/* Nodes */}
        {layers.map(layer =>
          (layer.nodes || []).map(node => {
            const pos = nodePos[node.node_id];
            if (!pos) return null;
            const color = getColor(node);
            const displayName = node.name.length > 4 ? node.name.slice(0, 4) : node.name;
            return (
              <g
                key={node.node_id}
                className="km-node"
                onClick={() => onNodeClick && onNodeClick(node.node_id, node.name)}
                style={{ cursor: 'pointer' }}
              >
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={NODE_R}
                  fill={color}
                  stroke="white"
                  strokeWidth={2}
                />
                <text
                  x={pos.x}
                  y={pos.y}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fill="white"
                  fontSize={9}
                  fontWeight={600}
                >
                  {displayName}
                </text>
              </g>
            );
          })
        )}

        {/* Legend */}
        <g transform={`translate(4, ${Math.max(svgH, 200) - 48})`}>
          {[
            { label: '已掌握', color: '#10b981' },
            { label: '进行中', color: '#f59e0b' },
            { label: '未解锁', color: '#d1d5db' },
          ].map((item, i) => (
            <g key={item.label} transform={`translate(0, ${i * 14})`}>
              <circle cx={5} cy={5} r={4} fill={item.color} />
              <text x={13} y={8} fontSize={9} fill="#6b7280">{item.label}</text>
            </g>
          ))}
        </g>
      </svg>
    </div>
  );
}
