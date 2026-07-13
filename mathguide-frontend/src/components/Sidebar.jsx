import DimMasteryList from './DimMasteryList';
import KnowledgeMap from './KnowledgeMap';
import './Sidebar.css';

export default function Sidebar({ dimData, collapsed, onToggle, onNodeClick, userId }) {
  if (collapsed) {
    return (
      <div className="sidebar collapsed">
        <div className="sidebar-collapsed-header">
          <span className="sidebar-label">当前掌握度</span>
          <button className="sidebar-toggle" onClick={onToggle}>🗺️</button>
        </div>
        <div className="sidebar-collapsed-list">
          {[...(dimData?.dimensions || [])]
            ?.sort((a, b) => a.mastery - b.mastery)
            .slice(0, 10)
            .map(d => (
              <div key={d.dim_id} className="sidebar-mini-row">
                <span className="sidebar-mini-name">{d.name}</span>
                <div className="sidebar-mini-bar">
                  <div
                    className="sidebar-mini-fill"
                    style={{
                      width: `${Math.round(d.mastery * 100)}%`,
                      background: d.mastery < 0.3 ? '#ef4444' : d.mastery < 0.6 ? '#f59e0b' : '#10b981',
                    }}
                  />
                </div>
                <span className="sidebar-mini-pct">{Math.round(d.mastery * 100)}%</span>
              </div>
            ))}
        </div>
      </div>
    );
  }

  return (
    <div className="sidebar expanded">
      <div className="sidebar-expanded-header">
        <button className="sidebar-toggle" onClick={onToggle}>← 收起</button>
      </div>
      <div className="sidebar-expanded-content">
        <div className="sidebar-map-section">
          <KnowledgeMap userId={userId} onNodeClick={onNodeClick} />
        </div>
        <div className="sidebar-list-section">
          <h4 className="sidebar-section-title">当前掌握度</h4>
          <DimMasteryList dimensions={dimData?.dimensions || []} />
        </div>
      </div>
    </div>
  );
}
