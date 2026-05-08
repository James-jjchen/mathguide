import './ErrorBanner.css';

export default function ErrorBanner({ message, onDismiss, onRetry }) {
  return (
    <div className="error-banner">
      <span className="error-icon">&#9888;</span>
      <span className="error-message">{message}</span>
      <div className="error-actions">
        {onRetry && (
          <button className="error-retry-btn" onClick={onRetry}>重试</button>
        )}
        {onDismiss && (
          <button className="error-dismiss-btn" onClick={onDismiss}>&times;</button>
        )}
      </div>
    </div>
  );
}
