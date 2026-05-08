import { useState, useEffect, useRef, useLayoutEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser } from '../context/UserContext';
import { getStageMap } from '../api/mathguide';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';
import EmptyState from '../components/EmptyState';
import './StageMapPage.css';

function EdgeSvg({ edges }) {
  return (
    <svg className="edge-svg" aria-hidden="true">
      {edges.map((e, i) => (
        <path
          key={i}
          d={e.path}
          className={`edge edge-${e.status}`}
          fill="none"
        />
      ))}
    </svg>
  );
}

function StageNode({ node, onClick }) {
  const status = node.status;
  const cls = `stage-node stage-node-${status}`;
  const clickable = status === 'unlocked' || status === 'cleared';

  return (
    <div
      className={cls}
      data-node-id={node.node_id}
      onClick={clickable ? () => onClick(node.node_id) : undefined}
      role={clickable ? 'button' : undefined}
      tabIndex={clickable ? 0 : undefined}
      onKeyDown={clickable ? (e) => { if (e.key === 'Enter') onClick(node.node_id); } : undefined}
      title={`${node.name} — ${status === 'cleared' ? '已通关' : status === 'unlocked' ? '可挑战' : '未解锁'} (掌握度: ${Math.round(node.mastery * 100)}%)`}
    >
      {status === 'locked' && <span className="node-lock-icon">&#128274;</span>}
      {status === 'cleared' && <span className="node-check-icon">&#10003;</span>}
      <span className="node-name">{node.name}</span>
      {status === 'cleared' && (
        <span className="node-mastery-badge">{Math.round(node.mastery * 100)}%</span>
      )}
    </div>
  );
}

export default function StageMapPage() {
  const { userId } = useUser();
  const navigate = useNavigate();
  const containerRef = useRef(null);

  const [layers, setLayers] = useState([]);
  const [prerequisites, setPrerequisites] = useState([]);
  const [summary, setSummary] = useState(null);
  const [edges, setEdges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadMap = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const data = await getStageMap(userId);
      setLayers(data.layers || []);
      setPrerequisites(data.prerequisites || []);
      setSummary(data.summary || null);
    } catch (err) {
      setError('加载闯关地图失败: ' + err.message);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    loadMap();
  }, [loadMap]);

  useLayoutEffect(() => {
    if (!containerRef.current || layers.length === 0) return;

    const containerRect = containerRef.current.getBoundingClientRect();
    const newEdges = [];

    for (const { from, to } of prerequisites) {
      const fromEl = containerRef.current.querySelector(`[data-node-id="${from}"]`);
      const toEl = containerRef.current.querySelector(`[data-node-id="${to}"]`);
      if (!fromEl || !toEl) continue;

      const fromRect = fromEl.getBoundingClientRect();
      const toRect = toEl.getBoundingClientRect();

      const x1 = fromRect.left - containerRect.left + fromRect.width / 2;
      const y1 = fromRect.bottom - containerRect.top;
      const x2 = toRect.left - containerRect.left + toRect.width / 2;
      const y2 = toRect.top - containerRect.top;

      const midY = (y1 + y2) / 2;
      const path = `M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`;

      // Determine edge status color
      const fromNode = layers.flatMap(l => l.nodes).find(n => n.node_id === from);
      const toNode = layers.flatMap(l => l.nodes).find(n => n.node_id === to);
      let status = 'locked';
      if (fromNode && toNode) {
        if (fromNode.status === 'cleared' && toNode.status === 'cleared') {
          status = 'cleared';
        } else if (fromNode.status === 'cleared' && toNode.status === 'unlocked') {
          status = 'unlocking';
        }
      }

      newEdges.push({ from, to, path, status });
    }

    setEdges(newEdges);
  }, [layers, prerequisites]);

  const handleNodeClick = (nodeId) => {
    navigate(`/stages/node/${nodeId}`);
  };

  if (loading) return <LoadingSpinner message="加载闯关地图..." />;

  if (error) return (
    <div className="stage-map-page">
      <ErrorBanner message={error} onRetry={loadMap} />
    </div>
  );

  if (summary && summary.cleared === summary.total) {
    return (
      <div className="stage-map-page">
        <EmptyState
          icon="&#127881;"
          title="恭喜通关！"
          description="你已掌握所有知识点，可以继续在问答模式中探索更深的问题。"
        />
      </div>
    );
  }

  return (
    <div className="stage-map-page">
      <div className="stage-map-header">
        <h2 className="page-title">闯关模式</h2>
        {summary && (
          <div className="stage-progress">
            <span className="progress-text">
              已通关 <strong>{summary.cleared}</strong> / {summary.total}
            </span>
            <div className="progress-bar-track">
              <div
                className="progress-bar-fill"
                style={{ width: `${(summary.cleared / summary.total) * 100}%` }}
              />
            </div>
          </div>
        )}
      </div>

      <p className="stage-hint">按前置关系逐层闯关，通关一个节点解锁其后续节点。点击蓝色节点开始挑战。</p>

      <div className="stage-legend">
        <span className="legend-item"><span className="legend-dot locked" /> 未解锁</span>
        <span className="legend-item"><span className="legend-dot unlocked" /> 可挑战</span>
        <span className="legend-item"><span className="legend-dot cleared" /> 已通关</span>
      </div>

      <div className="stage-map-container" ref={containerRef}>
        <EdgeSvg edges={edges} />
        <div className="stage-layers">
          {layers.map((layer) => (
            <div key={layer.layer} className="stage-layer">
              <span className="layer-label">第{layer.layer + 1}关</span>
              <div className="layer-nodes">
                {layer.nodes.map((node) => (
                  <StageNode key={node.node_id} node={node} onClick={handleNodeClick} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
