import { useState, useRef, useEffect, useCallback } from 'react';
import { askQuestionStream } from '../api/mathguide';
import LatexBlock from './LatexBlock';
import './ChatPanel.css';

export default function ChatPanel({ userId, initialQuestion = '', onClose }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState(initialQuestion);
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState('');
  const inputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const cancelRef = useRef(null);
  const lastInitialQuestionRef = useRef('');

  useEffect(() => {
    inputRef.current?.focus();
    return () => cancelRef.current?.();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamText]);

  const sendMessage = useCallback((text) => {
    const q = text || input.trim();
    if (!q || streaming) return;

    const userMsg = { role: 'user', content: q };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setStreaming(true);
    setStreamText('');

    let fullContent = '';

    cancelRef.current = askQuestionStream(q, userId, null, {
      onToken(token) {
        fullContent += token;
        setStreamText(fullContent);
      },
      onDone() {
        cancelRef.current = null;
        setMessages(prev => [...prev, { role: 'assistant', content: fullContent }]);
        setStreamText('');
        setStreaming(false);
      },
      onError(err) {
        cancelRef.current = null;
        setMessages(prev => [...prev, { role: 'assistant', content: `错误: ${err.message}` }]);
        setStreamText('');
        setStreaming(false);
      },
    });
  }, [input, streaming, userId]);

  useEffect(() => {
    if (!initialQuestion || initialQuestion === lastInitialQuestionRef.current) return;
    // Delay until after the effect commits. In development StrictMode the
    // first setup is cleaned up immediately, so only the committed setup sends.
    const timer = window.setTimeout(() => {
      lastInitialQuestionRef.current = initialQuestion;
      sendMessage(initialQuestion);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [initialQuestion, sendMessage]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }, [sendMessage]);

  const handleClose = useCallback(() => {
    cancelRef.current?.();
    cancelRef.current = null;
    onClose();
  }, [onClose]);

  return (
    <div className="chat-panel">
      <div className="chat-panel-header">
        <span>AI 助手</span>
        <button className="chat-close" onClick={handleClose}>×</button>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && !streamText && (
          <div className="chat-empty">
            <p>问我任何微积分问题</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`chat-msg ${msg.role}`}>
            <div className="chat-msg-content">
              <LatexBlock text={msg.content} />
            </div>
          </div>
        ))}
        {streamText && (
          <div className="chat-msg assistant">
            <div className="chat-msg-content">
              <LatexBlock text={streamText} />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <input
          ref={inputRef}
          type="text"
          className="chat-input"
          placeholder="输入问题..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={streaming}
        />
        <button
          className="chat-send"
          onClick={() => sendMessage()}
          disabled={!input.trim() || streaming}
        >
          发送
        </button>
      </div>
    </div>
  );
}
