import './EmptyState.css';

export default function EmptyState({ icon = '📚', title, description }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">{icon}</div>
      <h3 className="empty-title">{title}</h3>
      {description && <p className="empty-description">{description}</p>}
    </div>
  );
}
