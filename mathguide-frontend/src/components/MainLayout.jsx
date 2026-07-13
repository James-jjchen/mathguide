import { useState, useEffect, useCallback, useRef } from 'react';
import { getRecommendV2, getDimMastery, getProblemForDim, submitPracticeV2 } from '../api/mathguide';
import RecommendationCard from './RecommendationCard';
import PracticeOverlay from './PracticeOverlay';
import ChatPanel from './ChatPanel';
import Sidebar from './Sidebar';
import LoadingSpinner from './LoadingSpinner';
import ErrorBanner from './ErrorBanner';
import './MainLayout.css';

export default function MainLayout({ userId, onLogoActivate, onLogout }) {
  const [recommendations, setRecommendations] = useState([]);
  const [dimData, setDimData] = useState(null);
  const [momentum, setMomentum] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [chatOpen, setChatOpen] = useState(false);
  const [chatInitialQuestion, setChatInitialQuestion] = useState('');
  const [practice, setPractice] = useState(null); // { dimId, dimName, problem }
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [, setLogoClicks] = useState(0);
  const logoRef = useRef(null);
  const cardRefs = useRef({});

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [recData, dims] = await Promise.all([
        getRecommendV2(userId),
        getDimMastery(userId),
      ]);
      setRecommendations(recData.recommendations || []);
      setMomentum(recData.momentum || 0);
      setDimData(dims);
    } catch (e) {
      setError('加载数据失败: ' + e.message);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    // Data fetching is the external synchronization performed by this effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchData();
  }, [fetchData]);

  const handlePractice = useCallback(async (dimId, dimName) => {
    try {
      const data = await getProblemForDim(dimId);
      setPractice({ dimId, dimName, problem: data.problem });
    } catch {
      // If no problem found, open chat instead
      setChatInitialQuestion(`帮我练习 ${dimName}`);
      setChatOpen(true);
    }
  }, []);

  const handlePracticeComplete = useCallback(async (results) => {
    if (results && results.length > 0) {
      await submitPracticeV2(userId, results);
    }
    setPractice(null);
    await fetchData();
  }, [userId, fetchData]);

  const handleAskAI = useCallback((dimName) => {
    setChatInitialQuestion(`帮我理解 ${dimName}`);
    setChatOpen(true);
  }, []);

  const handleSearchFocus = useCallback(() => {
    setChatInitialQuestion('');
    setChatOpen(true);
  }, []);

  const handleSidebarNodeClick = useCallback((nodeId, nodeName) => {
    setChatInitialQuestion(`帮我了解 ${nodeName}`);
    setChatOpen(true);
  }, []);

  const handleLogoClick = useCallback(() => {
    setLogoClicks(prev => {
      const next = prev + 1;
      if (next >= 5) {
        onLogoActivate();
        return 0;
      }
      return next;
    });
  }, [onLogoActivate]);

  return (
    <div className="main-layout">
      <header className="main-header">
        <span
          ref={logoRef}
          className="main-logo"
          onClick={handleLogoClick}
        >
          MathGuide
        </span>
        <div className="search-bar" onClick={handleSearchFocus}>
          <span className="search-icon">🔍</span>
          <span className="search-placeholder">搜知识点 / 问问题...</span>
        </div>
        <div className="momentum-indicator">
          学习动量: <span className={momentum > 0 ? 'positive' : momentum < 0 ? 'negative' : ''}>
            {momentum > 0 ? '+' : ''}{momentum.toFixed(2)}
          </span>
        </div>
        <button className="main-logout" type="button" onClick={onLogout}>退出</button>
      </header>

      <div className="main-content">
        <div className="recommendation-area">
          {loading ? (
            <LoadingSpinner message="加载推荐中..." />
          ) : error ? (
            <ErrorBanner message={error} onRetry={fetchData} />
          ) : recommendations.length === 0 ? (
            <div className="empty-recommendations">
              <p>暂无推荐</p>
              <button className="btn-secondary" onClick={fetchData}>刷新</button>
            </div>
          ) : (
            <div className="cards-container">
              {recommendations.map((rec) => (
                <div key={`${rec.action_type}:${rec.target_dim}`} ref={el => { cardRefs.current[rec.target_dim] = el; }}>
                  <RecommendationCard
                    recommendation={rec}
                    onPractice={() => handlePractice(rec.target_dim, rec.target_dim_name)}
                    onAskAI={() => handleAskAI(rec.target_dim_name)}
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        <Sidebar
          dimData={dimData}
          collapsed={!sidebarExpanded}
          onToggle={() => setSidebarExpanded(prev => !prev)}
          onNodeClick={handleSidebarNodeClick}
          userId={userId}
        />
      </div>

      {chatOpen && (
        <ChatPanel
          userId={userId}
          initialQuestion={chatInitialQuestion}
          onClose={() => { setChatOpen(false); setChatInitialQuestion(''); }}
        />
      )}

      {practice && (
        <PracticeOverlay
          problem={practice.problem}
          dimId={practice.dimId}
          dimName={practice.dimName}
          userId={userId}
          onComplete={handlePracticeComplete}
          onClose={() => setPractice(null)}
          onAskAI={() => {
            setPractice(null);
            setChatInitialQuestion(`帮我理解 ${practice.dimName}`);
            setChatOpen(true);
          }}
        />
      )}
    </div>
  );
}
