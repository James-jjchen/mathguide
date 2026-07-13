import ProgressBar from './ProgressBar';
import './DimMasteryList.css';

export default function DimMasteryList({ dimensions }) {
  const sorted = [...dimensions]
    .sort((a, b) => a.mastery - b.mastery);

  return (
    <div className="dim-mastery-list">
      {sorted.map(d => (
        <div key={d.dim_id} className="dim-mastery-row" title={`α=${d.alpha} β=${d.beta} 卡住=${d.stuck_count}`}>
          <span className="dm-name">{d.name}</span>
          <div className="dm-bar-wrap">
            <ProgressBar value={d.mastery} color="auto" height={6} />
          </div>
          <span className="dm-pct">{Math.round(d.mastery * 100)}%</span>
        </div>
      ))}
    </div>
  );
}
