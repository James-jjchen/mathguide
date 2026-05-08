import { memo } from 'react';
import './MasteryBar.css';

const MasteryBar = memo(function MasteryBar({ nodeId, nodeName, mastery, compact = false }) {
  const pct = Math.round((mastery || 0) * 100);
  let colorClass = 'low';
  if (pct >= 60) colorClass = 'high';
  else if (pct >= 30) colorClass = 'medium';

  if (compact) {
    return (
      <div className="mastery-compact" title={`${nodeName}: ${pct}%`}>
        <span className={`mastery-dot ${colorClass}`} />
        <span className="mastery-name">{nodeName}</span>
        <span className="mastery-pct">{pct}%</span>
      </div>
    );
  }

  return (
    <div className="mastery-bar-container">
      <div className="mastery-label">
        <span className="mastery-name">{nodeName}</span>
        <span className="mastery-pct">{pct}%</span>
      </div>
      <div className="mastery-track">
        <div
          className={`mastery-fill ${colorClass}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
});

export default MasteryBar;
