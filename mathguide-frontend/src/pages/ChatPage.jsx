import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser } from '../context/UserContext';
import { askQuestion, askQuestionStream } from '../api/mathguide';
import ChatMessage from '../components/ChatMessage';
import ChatInput from '../components/ChatInput';
import MasteryBar from '../components/MasteryBar';
import ErrorBanner from '../components/ErrorBanner';
import EmptyState from '../components/EmptyState';
import './ChatPage.css';

const THINKING_WORDS = [
  '翻阅典籍', '奋笔疾书', '推演计算', '苦思冥想', '查阅笔记',
  '灵光一现', '条分缕析', '反复推敲', '抽丝剥茧', '略有所悟',
  '笔走龙蛇', '思如泉涌', '灵感迸发', '悉心演算', '斟酌推敲',
];

export default function ChatPage() {
  const {
    userId, nodes, mastery, initialized, refreshMastery,
    conversations, activeConvId, createConversation, deleteConversation, updateConversationTitle, setActiveConvId,
    messages, setMessages,
  } = useUser();

  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [thinkingIndex, setThinkingIndex] = useState(() => Math.floor(Math.random() * THINKING_WORDS.length));
  const [dotCount, setDotCount] = useState(0);
  const [activeQ, setActiveQ] = useState(-1);
  const [showMastery, setShowMastery] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const editInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const msgRefs = useRef({});
  const cancelRef = useRef(null);
  const navigate = useNavigate();

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    if (!sending) {
      setThinkingIndex(Math.floor(Math.random() * THINKING_WORDS.length));
      setDotCount(0);
      return;
    }
    const wordTimer = setInterval(() => {
      setThinkingIndex((prev) => {
        let next;
        do { next = Math.floor(Math.random() * THINKING_WORDS.length); }
        while (next === prev && THINKING_WORDS.length > 1);
        return next;
      });
    }, 20000);
    const dotTimer = setInterval(() => {
      setDotCount((prev) => (prev + 1) % 4);
    }, 420);
    return () => { clearInterval(wordTimer); clearInterval(dotTimer); };
  }, [sending]);

  useEffect(() => { scrollToBottom(); }, [messages, scrollToBottom]);

  const handleSend = async (question) => {
    setError(null);
    const userMsg = { role: 'user', content: question, timestamp: Date.now() };
    setMessages((prev) => [...prev, userMsg]);
    setSending(true);

    const learnedIds = Object.entries(mastery)
      .filter(([, v]) => v >= 0.7)
      .map(([k]) => parseInt(k));
    const ids = learnedIds.length > 0 ? learnedIds : null;

    let content = '';
    let resolved = false;

    const doFallback = async () => {
      if (resolved || content) return;
      resolved = true;
      try {
        const data = await askQuestion(question, userId, ids);
        setSending(false);
        setMessages((prev) => [...prev, { role: 'assistant', content: data.answer, timestamp: Date.now() }]);
        refreshMastery();
      } catch (err) {
        setSending(false);
        setError('发送失败: ' + err.message);
      }
    };

    cancelRef.current = askQuestionStream(question, userId, ids, {
      onThinking() {},
      onToken(token) {
        if (!content) setSending(false);
        content += token;
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === 'assistant' && last._streaming) {
            return [...prev.slice(0, -1), { ...last, content }];
          }
          return [...prev, { role: 'assistant', content, timestamp: Date.now(), _streaming: true }];
        });
      },
      onDone() {
        if (resolved) return;
        resolved = true;
        if (!content) { doFallback(); return; }
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === 'assistant' && last._streaming) {
            const { _streaming, ...msg } = last;
            return [...prev.slice(0, -1), msg];
          }
          return prev;
        });
        refreshMastery();
      },
      onError() { doFallback(); },
    });
  };

  const handleStop = () => {
    cancelRef.current?.();
    cancelRef.current = null;
    setSending(false);
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (last?.role === 'assistant' && last._streaming) {
        const { _streaming, ...msg } = last;
        return [...prev.slice(0, -1), msg];
      }
      return prev;
    });
  };

  const weakNodes = Object.entries(mastery)
    .filter(([, v]) => v < 0.5)
    .sort(([, a], [, b]) => a - b);

  // Question navigation
  const questions = messages
    .map((m, i) => (m.role === 'user' ? { index: i, text: m.content } : null))
    .filter(Boolean);

  const scrollToMsg = (index) => {
    setActiveQ(index);
    msgRefs.current[index]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  useEffect(() => {
    if (questions.length > 0) setActiveQ(questions[questions.length - 1].index);
  }, [messages.length]);

  // Conversation list sorted newest first
  const convList = Object.values(conversations).sort((a, b) => b.createdAt - a.createdAt);

  return (
    <div className="chat-page">
      {/* Left: conversation sidebar */}
      <aside className="conv-sidebar">
        <button className="conv-new-btn" onClick={createConversation}>+ 新对话</button>
        <div className="conv-list">
          {convList.map((c) => (
            <div
              key={c.id}
              className={`conv-item${c.id === activeConvId ? ' active' : ''}`}
              onClick={() => setActiveConvId(c.id)}
              onDoubleClick={() => { setEditingId(c.id); setTimeout(() => editInputRef.current?.select(), 0); }}
            >
              {editingId === c.id ? (
                <input
                  ref={editInputRef}
                  className="conv-edit-input"
                  defaultValue={c.title}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') { updateConversationTitle(c.id, e.target.value); setEditingId(null); }
                    if (e.key === 'Escape') setEditingId(null);
                  }}
                  onBlur={(e) => { updateConversationTitle(c.id, e.target.value); setEditingId(null); }}
                  onClick={(e) => e.stopPropagation()}
                />
              ) : (
                <span className="conv-title">{c.title}</span>
              )}
              {convList.length > 1 && (
                <button
                  className="conv-del"
                  onClick={(e) => { e.stopPropagation(); deleteConversation(c.id); }}
                  title="删除对话"
                >×</button>
              )}
            </div>
          ))}
        </div>
      </aside>

      {/* Main chat area */}
      <main className="chat-main">
        {/* Header bar with mastery toggle */}
        <div className="chat-topbar">
          <span className="chat-conv-title">{conversations[activeConvId]?.title || ''}</span>
          <button
            className={`mastery-toggle${showMastery ? ' active' : ''}`}
            onClick={() => setShowMastery((v) => !v)}
          >
            掌握度
          </button>
        </div>

        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

        <div className="messages-container">
          {messages.length === 0 ? (
            <EmptyState
              icon="&#128218;"
              title="开始你的微积分学习之旅！"
              description="提出数学问题，系统将为你解答并分析掌握情况。支持LaTeX公式和分步骤讲解。"
            />
          ) : (
            messages.map((msg, i) => (
              <div
                key={i}
                ref={(el) => { msgRefs.current[i] = el; }}
                className={`msg-wrapper ${msg.role}`}
              >
                <ChatMessage message={msg} isUser={msg.role === 'user'} />
              </div>
            ))
          )}
          {sending && (
            <div className="chat-message assistant">
              <div className="message-bubble thinking-bubble">
                <span className="thinking-text">{THINKING_WORDS[thinkingIndex]}</span>
                <span className="thinking-dots">{'.'.repeat(dotCount)}</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {weakNodes.length > 0 && messages.length > 0 && (
          <div className="weakness-prompt">
            <span>检测到 {weakNodes.length} 个薄弱知识点</span>
            <button className="practice-btn" onClick={() => navigate('/practice')}>去练习</button>
          </div>
        )}

        <ChatInput onSend={handleSend} onStop={handleStop} disabled={sending} />
      </main>

      {/* Right: question nav bars */}
      {questions.length > 0 && (
        <div className="qnav-strip">
          {questions.slice(-5).map((q) => (
            <span key={q.index} className="qnav-bar-slot">
              <span className="qnav-bar" />
            </span>
          ))}
          <div className="qnav-popup">
            <div className="qnav-list">
              {questions.map((q) => (
                <button
                  key={q.index}
                  className={`qnav-item${activeQ === q.index ? ' active' : ''}`}
                  onClick={() => scrollToMsg(q.index)}
                >
                  <span className="qnav-index">Q{questions.indexOf(q) + 1}</span>
                  <span className="qnav-text">{q.text.slice(0, 36)}{q.text.length > 36 ? '…' : ''}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Floating mastery panel */}
      {showMastery && (
        <div className="mastery-panel">
          <div className="mastery-panel-header">
            <h3>掌握度总览</h3>
            <button className="mastery-close" onClick={() => setShowMastery(false)}>×</button>
          </div>
          <div className="mastery-panel-list">
            {nodes.map((node) => (
              <MasteryBar key={node.id} nodeId={node.id} nodeName={node.name} mastery={mastery[node.id] || 0} compact />
            ))}
            {nodes.length === 0 && <p className="mastery-empty">暂无知识点数据</p>}
          </div>
        </div>
      )}
    </div>
  );
}
