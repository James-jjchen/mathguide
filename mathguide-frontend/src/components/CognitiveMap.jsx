import { useState, useEffect, useRef, useLayoutEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { getStageMap } from '../api/mathguide';
import LoadingSpinner from './LoadingSpinner';
import ErrorBanner from './ErrorBanner';
import './CognitiveMap.css';

const NODE_RADIUS = 22;
const LAYER_GAP = 100;
const NODE_GAP = 30;
const PADDING = 30;

function getNodeColor(mastery, status) {
  if (status === 'cleared' || mastery >= 0.7) return { fill: '#10b981', stroke: '#059669', label: '已掌握' };
  if (status === 'unlocked' || (mastery >= 0.5 && mastery < 0.7)) return { fill: '#f59e0b', stroke: '#d97706', label: '进行中' };
  if (mastery >= 0.3 && mastery < 0.5) return { fill: '#f97316', stroke: '#ea580c', label: '薄弱' };
  return { fill: '#ef4444', stroke: '#dc2626', label: '未掌握' };
}

export default function CognitiveMap({ userId, collapsed: controlledCollapsed, onToggle }) {
  const navigate = useNavigate();
  const svgRef = useRef(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [collapsed, setCollapsed] = useState(true);

  const isCollapsed = controlledCollapsed !== undefined ? controlledCollapsed : collapsed;
  const toggle = onToggle || (() => setCollapsed((v) => !v));

  useEffect(() => {
    if (!userId) return;
    setLoading(true);
    setError(null);
    getStageMap(userId)
      .then(setData)
      .catch((err) => setError('加载认知地图失败: ' + err.message))
      .finally(() => setLoading(false));
  }, [userId]);

  const { nodes, edges, svgSize } = useMemo(() => {
    if (!data?.layers) return { nodes: [], edges: [], svgSize: { w: 400, h: 200 } };

    const allNodes = [];
    const nodePositions = {};
    let maxW = 400;

    for (let li = 0; li < data.layers.length; li++) {
      const layer = data.layers[li];
      const nCount = layer.nodes.length;
      const totalW = nCount * (NODE_RADIUS * 2) + (nCount - 1) * NODE_GAP;

      for (let ni = 0; ni < nCount; ni++) {
        const node = layer.nodes[ni];
        const x = PADDING + NODE_RADIUS + ni * (NODE_RADIUS * 2 + NODE_GAP) + (maxW - totalW - PADDING * 2) / 2;
        const y = PADDING + NODE_RADIUS + li * (NODE_RADIUS * 2 + LAYER_GAP);

        const pos = { x, y };
        allNodes.push({ ...node, ...pos });
        nodePositions[node.node_id] = pos;
      }

      const rowW = totalW + PADDING * 2;
      if (rowW > maxW) maxW = rowW;
    }

    const edgeList = [];
    for (const { from, to } of data.prerequisites || []) {
      const fp = nodePositions[from];
      const tp = nodePositions[to];
      if (!fp || !tp) continue;

      const fromNode = allNodes.find((n) => n.node_id === from);
      const toNode = allNodes.find((n) => n.node_id === to);
      let status = 'locked';
      if (fromNode && toNode) {
        if (fromNode.status === 'cleared' && toNode.status === 'cleared') status = 'cleared';
        else if (fromNode.status === 'cleared' && toNode.status === 'unlocked') status = 'unlocked';
      }

      const dx = tp.x - fp.x;
      const dy = tp.y - fp.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const nx = dx / dist;
      const ny = dy / dist;

      edgeList.push({
        from, to, status,
        x1: fp.x + nx * NODE_RADIUS,
        y1: fp.y + ny * NODE_RADIUS,
        x2: tp.x - nx * NODE_RADIUS,
        y2: tp.y - ny * NODE_RADIUS,
      });
    }

    const h = PADDING * 2 + data.layers.length * (NODE_RADIUS * 2 + LAYER_GAP) - LAYER_GAP;
    return { nodes: allNodes, edges: edgeList, svgSize: { w: Math.max(maxW, 600), h: Math.max(h, 200) } };
  }, [data]);

  useLayoutEffect(() => {
    const el = svgRef.current?.parentElement;
    if (el) el.scrollLeft = (svgSize.w - el.clientWidth) / 2;
  }, [svgSize]);

  if (isCollapsed) {
    return (
      <div className="cm-collapsed" onClick={toggle}>
        <span className="cm-collapsed-icon">🧠</span>
        <span>认知地图</span>
        <span className="cm-expand-hint">点击展开</span>
      </div>
    );
  }

  if (loading) return <LoadingSpinner message="加载认知地图..." />;

  if (error) return (
    <div className="cm-section">
      <div className="cm-header">
        <h3 className="cm-title">认知地图</h3>
        <button className="cm-collapse-btn" onClick={toggle}>收起</button>
      </div>
      <ErrorBanner message={error} onDismiss={() => setError(null)} />
    </div>
  );

  if (!data) return null;

  return (
    <div className="cm-section">
      <div className="cm-header">
        <h3 className="cm-title">认知地图</h3>
        <button className="cm-collapse-btn" onClick={toggle}>收起</button>
      </div>

      <div className="cm-legend">
        <span className="cm-legend-item"><span className="cm-legend-dot" style={{ background: '#10b981' }} /> 已掌握</span>
        <span className="cm-legend-item"><span className="cm-legend-dot" style={{ background: '#f59e0b' }} /> 进行中</span>
        <span className="cm-legend-item"><span className="cm-legend-dot" style={{ background: '#f97316' }} /> 薄弱</span>
        <span className="cm-legend-item"><span className="cm-legend-dot" style={{ background: '#ef4444' }} /> 未掌握</span>
        <span className="cm-legend-item" style={{ marginLeft: 'auto' }}>
          <span className="cm-legend-arrow" /> 前置依赖
        </span>
      </div>

      <div className="cm-svg-wrap">
        <svg
          ref={svgRef}
          className="cm-svg"
          viewBox={`0 0 ${svgSize.w} ${svgSize.h}`}
          style={{ minWidth: svgSize.w }}
        >
          {/* Arrowhead marker */}
          <defs>
            <marker id="cm-arrow-cleared" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#10b981" />
            </marker>
            <marker id="cm-arrow-unlocked" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#3b82f6" />
            </marker>
            <marker id="cm-arrow-locked" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#d1d5db" />
            </marker>
          </defs>

          {/* Edges */}
          {edges.map((e, i) => (
            <line
              key={i}
              x1={e.x1} y1={e.y1} x2={e.x2} y2={e.y2}
              className={`cm-edge cm-edge-${e.status}`}
              markerEnd={`url(#cm-arrow-${e.status})`}
            />
          ))}

          {/* Nodes */}
          {nodes.map((node) => {
            const colors = getNodeColor(node.mastery, node.status);
            const clickable = node.status === 'unlocked' || node.status === 'cleared';
            return (
              <g
                key={node.node_id}
                className={`cm-node ${clickable ? 'cm-node-clickable' : ''}`}
                transform={`translate(${node.x}, ${node.y})`}
                onClick={clickable ? () => navigate(`/stages/node/${node.node_id}`) : undefined}
              >
                <circle
                  r={NODE_RADIUS}
                  fill={colors.fill}
                  stroke={colors.stroke}
                  strokeWidth="2"
                />
                <text
                  textAnchor="middle"
                  dy="0.35em"
                  fontSize="10"
                  fontWeight="600"
                  fill="white"
                >
                  {node.name.length > 4 ? node.name.slice(0, 4) : node.name}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
