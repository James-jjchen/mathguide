import { useState, useEffect } from 'react';
import { getRecommendV2 } from '../api/mathguide';
import LoadingSpinner from './LoadingSpinner';
import ErrorBanner from './ErrorBanner';
import './RecommendationPanel.css';

const ACTION_CONFIG = {
  bottleneck:  { badge: '🔴', label: '瓶颈突破', color: '#ef4444' },
  unlock:      { badge: '🟢', label: '即将解锁', color: '#10b981' },
  transfer:    { badge: '🟡', label: '横向转移', color: '#f59e0b' },
  recovery:    { badge: '🔵', label: '动量恢复', color: '#3b82f6' },
  discovery:   { badge: '🟣', label: '探索发现', color: '#8b5cf6' },
};

function ScoreBar({ score }) {
  const pct = Math.min(score / 2, 1) * 100;
  let barColor = '#ef4444';
  if (score >= 1.5) barColor = '#10b981';
  else if (score >= 1.0) barColor = '#3b82f6';
  else if (score >= 0.5) barColor = '#f59e0b';

  return (
    <div className="rp-score-bar-track">
      <div
        className="rp-score-bar-fill"
        style={{ width: `${pct}%`, background: barColor }}
      />
      <span className="rp-score-label">{score.toFixed(2)}</span>
    </div>
  );
}

function MomentumIndicator({ momentum }) {
  const pct = ((momentum + 1) / 2) * 100;
  let color = '#10b981';
  let label = '积极';
  if (momentum < -0.3) { color = '#ef4444'; label = '低迷'; }
  else if (momentum < 0) { color = '#f59e0b'; label = '一般'; }
  else if (momentum < 0.3) { color = '#3b82f6'; label = '良好'; }

  return (
    <div className="rp-momentum">
      <span className="rp-momentum-label">学习动量</span>
      <div className="rp-momentum-track">
        <div
          className="rp-momentum-fill"
          style={{ width: `${pct}%`, background: color }}
        />
        <span className="rp-momentum-value" style={{ color }}>
          {momentum > 0 ? '+' : ''}{momentum.toFixed(2)} {label}
        </span>
      </div>
    </div>
  );
}

export default function RecommendationPanel({ userId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getRecommendV2(userId);
      setData(result);
    } catch (err) {
      setError('加载推荐失败: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [userId]);

  if (loading) return <LoadingSpinner message="加载推荐..." />;

  if (error) return <ErrorBanner message={error} onDismiss={() => setError(null)} onRetry={loadData} />;

  const recs = data?.recommendations || [];
  const momentum = data?.momentum ?? 0;

  return (
    <div className="rp-panel">
      <div className="rp-header">
        <h3 className="rp-title">智能学习推荐</h3>
        <button className="rp-refresh-btn" onClick={loadData} title="刷新推荐">
          🔄 刷新
        </button>
      </div>

      <MomentumIndicator momentum={momentum} />

      {recs.length === 0 ? (
        <p className="rp-empty">暂无推荐，继续学习以获取个性化建议</p>
      ) : (
        <div className="rp-cards">
          {recs.map((rec, i) => {
            const cfg = ACTION_CONFIG[rec.action_type] || ACTION_CONFIG.discovery;
            return (
              <div key={i} className="rp-card" style={{ borderLeftColor: cfg.color }}>
                <div className="rp-card-header">
                  <span className="rp-badge" style={{ background: cfg.color + '18', color: cfg.color }}>
                    {cfg.badge} {cfg.label}
                  </span>
                  <ScoreBar score={rec.score} />
                </div>
                <div className="rp-card-body">
                  <span className="rp-dim-name">{rec.target_dim_name}</span>
                  <p className="rp-explanation">{rec.explanation}</p>
                </div>
                {rec.affected_dims && rec.affected_dims.length > 0 && (
                  <div className="rp-affected">
                    <span className="rp-affected-label">相关维度:</span>
                    {rec.affected_dims.map((d) => (
                      <span key={d} className="rp-dim-tag">{d}</span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {data?.user_state_summary && (
        <div className="rp-summary-row">
          <span>维度总数: <strong>{data.user_state_summary.dim_count}</strong></span>
          <span>薄弱维度: <strong>{data.user_state_summary.weak_dims}</strong></span>
          <span>平均掌握度: <strong>{(data.user_state_summary.avg_mastery * 100).toFixed(0)}%</strong></span>
        </div>
      )}
    </div>
  );
}
