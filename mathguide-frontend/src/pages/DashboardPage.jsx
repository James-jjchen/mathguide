import { useState, useEffect, useMemo } from 'react';
import { useUser } from '../context/UserContext';
import { diagnoseWeaknesses, resetMastery, resetAll } from '../api/mathguide';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ResponsiveContainer } from 'recharts';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';
import RecommendationPanel from '../components/RecommendationPanel';
import CognitiveMap from '../components/CognitiveMap';
import './DashboardPage.css';

const CHAPTER_COLORS = ['#3b82f6', '#8b5cf6', '#10b981'];

export default function DashboardPage() {
  const { userId, nodes, chapters, mastery, setMastery, setInitialized, refreshNodes, reset } = useUser();

  const [weaknesses, setWeaknesses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [resetConfirm, setResetConfirm] = useState(null); // 'mastery' | 'all' | null
  const [resetting, setResetting] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const weakData = await diagnoseWeaknesses(userId);
      setWeaknesses(weakData.weaknesses || []);
    } catch (err) {
      setError('加载数据失败: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleResetMastery = async () => {
    setResetting(true);
    setError(null);
    try {
      await resetMastery(userId);
      setMastery({});
      await loadData();
      setResetConfirm(null);
    } catch (err) {
      setError('重置掌握度失败: ' + err.message);
    } finally {
      setResetting(false);
    }
  };

  const handleResetAll = async () => {
    setResetting(true);
    setError(null);
    try {
      await resetAll();
      setMastery({});
      setInitialized(false);
      await refreshNodes();
      setResetConfirm(null);
    } catch (err) {
      setError('恢复原始配置失败: ' + err.message);
    } finally {
      setResetting(false);
    }
  };

  // Chapter average mastery
  const chapterData = useMemo(() => {
    return chapters.map((ch) => {
      const chapterNodes = nodes.filter((n) => n.chapter_id === ch.chapter_id);
      const values = chapterNodes.map((n) => mastery[n.id] || 0);
      const avg = values.length > 0
        ? Math.round((values.reduce((a, b) => a + b, 0) / values.length) * 100)
        : 0;
      return {
        name: ch.chapter_name.length > 4 ? ch.chapter_name.slice(0, 5) + '...' : ch.chapter_name,
        fullName: ch.chapter_name,
        掌握度: avg,
      };
    });
  }, [chapters, nodes, mastery]);

  // Mastery distribution
  const distribution = useMemo(() => {
    const ranges = [
      { label: '未掌握', min: 0, max: 0.2, color: '#ef4444' },
      { label: '薄弱', min: 0.2, max: 0.5, color: '#f59e0b' },
      { label: '发展中', min: 0.5, max: 0.7, color: '#3b82f6' },
      { label: '较熟练', min: 0.7, max: 0.9, color: '#10b981' },
      { label: '精通', min: 0.9, max: 1.0, color: '#059669' },
    ];
    return ranges.map((r) => {
      const count = Object.values(mastery).filter((m) => m >= r.min && m < r.max).length;
      return { ...r, count };
    });
  }, [mastery]);

  const overallAvg = useMemo(() => {
    const values = Object.values(mastery);
    return values.length > 0
      ? Math.round((values.reduce((a, b) => a + b, 0) / values.length) * 100)
      : 0;
  }, [mastery]);

  if (loading) return <LoadingSpinner message="加载中..." />;

  return (
    <div className="dashboard-page">
      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} onRetry={loadData} />}

      {/* Profile header */}
      <div className="profile-header">
        <div className="profile-avatar">
          <span className="avatar-text">{userId.charAt(0).toUpperCase()}</span>
        </div>
        <div className="profile-info">
          <h2 className="profile-name">{userId}</h2>
          <p className="profile-meta">
            已掌握 {distribution[3].count + distribution[4].count} / {nodes.length} 个知识点
          </p>
        </div>
        <div className="profile-stats">
          <div className="profile-stat">
            <span className="stat-value">{overallAvg}%</span>
            <span className="stat-label">总体掌握度</span>
          </div>
          <div className="profile-stat">
            <span className="stat-value">{distribution[3].count + distribution[4].count}</span>
            <span className="stat-label">已掌握</span>
          </div>
          <div className="profile-stat">
            <span className="stat-value">{weaknesses.length}</span>
            <span className="stat-label">薄弱点</span>
          </div>
        </div>
        <button className="profile-logout-btn" onClick={reset}>退出登录</button>
      </div>

      <div className="dashboard-grid">
        {/* Overall average */}
        <div className="dash-card overall-card">
          <h3 className="card-title">总体掌握度</h3>
          <div className="overall-value">{overallAvg}%</div>
          <div className="overall-track">
            <div className="overall-fill" style={{ width: `${overallAvg}%` }} />
          </div>
        </div>

        {/* Chapter mastery chart */}
        <div className="dash-card chart-card">
          <h3 className="card-title">章节掌握度</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chapterData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
              <Tooltip
                formatter={(value) => [`${value}%`, '掌握度']}
                labelFormatter={(label, payload) => payload?.[0]?.payload?.fullName || label}
              />
              <Bar dataKey="掌握度" radius={[4, 4, 0, 0]}>
                {chapterData.map((_, i) => (
                  <Cell key={i} fill={CHAPTER_COLORS[i]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Distribution */}
        <div className="dash-card">
          <h3 className="card-title">知识点分布</h3>
          <div className="distribution">
            {distribution.map((d) => (
              <div key={d.label} className="dist-row">
                <span className="dist-label">{d.label}</span>
                <div className="dist-bar-track">
                  <div
                    className="dist-bar-fill"
                    style={{
                      width: nodes.length > 0 ? `${(d.count / nodes.length) * 100}%` : '0%',
                      background: d.color,
                    }}
                  />
                </div>
                <span className="dist-count">{d.count}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Recommendation v2 */}
        <div className="dash-card dash-card-full">
          <RecommendationPanel userId={userId} />
        </div>

        {/* Weakness summary */}
        <div className="dash-card">
          <h3 className="card-title">薄弱知识点</h3>
          {weaknesses.length > 0 ? (
            <div className="weak-list">
              {weaknesses.slice(0, 5).map((w) => (
                <div key={w.node_id} className="weak-item">
                  <span className={`weak-priority ${w.priority}`} />
                  <span className="weak-name">{w.name}</span>
                  <span className="weak-value">{Math.round(w.mastery * 100)}%</span>
                </div>
              ))}
              {weaknesses.length > 5 && (
                <p className="weak-more">还有 {weaknesses.length - 5} 个薄弱知识点...</p>
              )}
            </div>
          ) : (
            <p className="rec-empty">暂无薄弱知识点，继续保持！</p>
          )}
        </div>

        {/* Reset settings */}
        <div className="dash-card reset-card">
          <h3 className="card-title">数据管理</h3>
          <div className="reset-actions">
            <button
              className="reset-btn reset-btn-mastery"
              onClick={() => setResetConfirm('mastery')}
              disabled={resetting}
            >
              重置掌握度
            </button>
            <button
              className="reset-btn reset-btn-all"
              onClick={() => setResetConfirm('all')}
              disabled={resetting}
            >
              恢复原始配置
            </button>
          </div>
          <p className="reset-hint">
            重置掌握度将清空学习进度；恢复原始配置将重置整个数据库
          </p>

          {resetConfirm && (
            <div className="reset-confirm-overlay">
              <div className="reset-confirm-box">
                <p className="reset-confirm-text">
                  {resetConfirm === 'mastery'
                    ? '确定要重置所有知识点的掌握度吗？学习进度将全部丢失。'
                    : '确定要恢复原始配置吗？所有数据（包括所有用户的掌握度）将被清除并重新导入。'}
                </p>
                <div className="reset-confirm-btns">
                  <button
                    className="reset-confirm-btn reset-confirm-yes"
                    onClick={resetConfirm === 'mastery' ? handleResetMastery : handleResetAll}
                    disabled={resetting}
                  >
                    {resetting ? '处理中...' : '确定'}
                  </button>
                  <button
                    className="reset-confirm-btn reset-confirm-no"
                    onClick={() => setResetConfirm(null)}
                    disabled={resetting}
                  >
                    取消
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Cognitive Map */}
      <CognitiveMap userId={userId} />
    </div>
  );
}
