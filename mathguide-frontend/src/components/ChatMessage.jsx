import LatexBlock from './LatexBlock';
import './ChatMessage.css';

export default function ChatMessage({ message, isUser }) {
  const content = message?.content || '';
  const involvedNodes = message?.involved_nodes;
  const timestamp = message?.timestamp;

  return (
    <div className={`chat-message ${isUser ? 'user' : 'assistant'}`}>
      <div className="message-bubble">
        {isUser ? (
          <p className="message-text">{content}</p>
        ) : (
          <div className="message-text">
            <LatexBlock content={content} />
          </div>
        )}
        {Array.isArray(involvedNodes) && involvedNodes.length > 0 && (
          <div className="involved-nodes">
            <span className="nodes-label">涉及知识点：</span>
            {involvedNodes.map((node, idx) => {
              const name = node?.name || node?.node_name || '?';
              const conf = typeof node?.confidence === 'number' ? node.confidence : 0;
              return (
                <span key={node?.node_id || idx} className="node-chip" title={`置信度: ${Math.round(conf * 100)}%`}>
                  {name}
                  <span className="node-confidence">{Math.round(conf * 100)}%</span>
                </span>
              );
            })}
          </div>
        )}
        {timestamp && <div className="message-time">{formatTime(timestamp)}</div>}
      </div>
    </div>
  );
}

function formatTime(ts) {
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}
