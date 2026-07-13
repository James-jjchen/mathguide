export default function ProgressBar({ value, max = 1, color = '#10b981', height = 8, showLabel = false }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  let barColor = color;
  if (!color || color === 'auto') {
    if (pct < 30) barColor = '#ef4444';
    else if (pct < 60) barColor = '#f59e0b';
    else barColor = '#10b981';
  }
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}>
      <div style={{
        flex: 1,
        height,
        background: '#e5e7eb',
        borderRadius: height / 2,
        overflow: 'hidden',
      }}>
        <div style={{
          width: `${pct}%`,
          height: '100%',
          background: barColor,
          borderRadius: height / 2,
          transition: 'width 0.5s ease',
        }} />
      </div>
      {showLabel && (
        <span style={{ fontSize: 12, color: '#6b7280', minWidth: 36, textAlign: 'right' }}>
          {pct}%
        </span>
      )}
    </div>
  );
}
