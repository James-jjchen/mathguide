import { useState, useRef, useCallback } from 'react';
import './ChatInput.css';

const MAX_CHARS = 2000;

export default function ChatInput({ onSend, onStop, disabled }) {
  const [text, setText] = useState('');
  const textareaRef = useRef(null);

  const handleSubmit = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [text, disabled, onSend]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }, [handleSubmit]);

  const handleInput = useCallback((e) => {
    const el = e.target;
    setText(el.value);
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  }, []);

  const charCount = text.length;
  const overLimit = charCount > MAX_CHARS;

  return (
    <div className="chat-input-container">
      <textarea
        ref={textareaRef}
        className={`chat-textarea ${overLimit ? 'over-limit' : ''}`}
        value={text}
        onChange={handleInput}
        onKeyDown={handleKeyDown}
        placeholder="输入你的数学问题...（Enter发送，Shift+Enter换行）"
        rows={1}
        disabled={disabled}
        maxLength={MAX_CHARS + 100}
      />
      <div className="chat-input-footer">
        <span className={`char-count ${overLimit ? 'over-limit' : ''}`}>
          {charCount}/{MAX_CHARS}
        </span>
        {onStop && disabled && (
          <button className="stop-btn" onClick={onStop}>停止生成</button>
        )}
        <button
          className="send-button"
          onClick={handleSubmit}
          disabled={disabled || !text.trim() || overLimit}
        >
          发送
        </button>
      </div>
    </div>
  );
}
