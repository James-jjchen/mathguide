import { useState, useEffect } from 'react';
import { getChapters, getNodes, generatePractice, submitPractice } from '../api/mathguide';
import LatexBlock from './LatexBlock';
import LoadingSpinner from './LoadingSpinner';
import './Onboarding.css';

const LEVELS = [
  { key: 'beginner', label: '从零开始', desc: '我刚开始学微积分，需要系统学习' },
  { key: 'partial', label: '学过一些，想查漏补缺', desc: '我有一定基础，想找到薄弱点提升' },
  { key: 'review', label: '需要巩固复习', desc: '我学过微积分，需要系统复习巩固' },
];

export default function Onboarding({ onComplete }) {
  const [step, setStep] = useState(1);
  const [nickname, setNickname] = useState('');
  const [level, setLevel] = useState('');
  const [chapters, setChapters] = useState([]);
  const [nodes, setNodes] = useState([]);
  const [nodeRatings, setNodeRatings] = useState({});
  const [expandedChapter, setExpandedChapter] = useState(null);
  const [quizQuestions, setQuizQuestions] = useState([]);
  const [quizAnswers, setQuizAnswers] = useState({});
  const [quizSubmitted, setQuizSubmitted] = useState(false);
  const [quizResults, setQuizResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (step === 2) {
      loadData();
    }
  }, [step]);

  async function loadData() {
    setLoading(true);
    try {
      const [chaps, allNodes] = await Promise.all([getChapters(), getNodes()]);
      setChapters(chaps);
      setNodes(allNodes);
    } catch (e) {
      setError('加载数据失败: ' + e.message);
    } finally {
      setLoading(false);
    }
  }

  const nicknameValid = nickname.trim().length >= 1;
  const markedCount = Object.keys(nodeRatings).length;
  const totalNodes = nodes.length;

  async function handleNext() {
    if (step === 1) {
      if (!nicknameValid) return;
      if (level === 'beginner') {
        setLoading(true);
        setError('');
        try {
          await onComplete(nickname.trim(), {});
        } catch (e) {
          setError('初始化失败: ' + e.message);
          setLoading(false);
        }
        return;
      }
      if (level === 'review') {
        setLoading(true);
        try {
          const allNodes = await getNodes();
          const mastery = {};
          allNodes.forEach(n => { mastery[n.id] = 0.4; });
          await onComplete(nickname.trim(), mastery);
        } catch (e) {
          setError('初始化失败: ' + e.message);
        } finally {
          setLoading(false);
        }
        return;
      }
      setStep(2);
    }
  }

  function handleStart() {
    if (step === 2) {
      const hasProficient = Object.values(nodeRatings).some(v => v > 0.5);
      if (hasProficient) {
        startQuiz();
        return;
      }
      finishOnboarding();
      return;
    }
  }

  async function startQuiz() {
    setStep(3);
    setLoading(true);
    const proficientNodeIds = Object.entries(nodeRatings)
      .filter(([, v]) => v > 0.5)
      .map(([id]) => parseInt(id));
    try {
      const result = await generatePractice(
        'temp_' + Date.now(),
        proficientNodeIds.slice(0, 3),
        Math.min(proficientNodeIds.length, 3)
      );
      setQuizQuestions(result.questions || []);
    } catch (e) {
      setError('生成测试题失败: ' + e.message);
    } finally {
      setLoading(false);
    }
  }

  async function submitQuiz() {
    setLoading(true);
    const userId = nickname.trim();
    const answers = quizQuestions.map(q => ({
      question_id: q.id || 'q_' + Date.now(),
      node_id: q.node_id,
      question_text: q.text || q.question || '',
      student_answer: quizAnswers[q.id] || '',
    }));
    try {
      const result = await submitPractice(userId, answers);
      setQuizResults(result);
      setQuizSubmitted(true);
    } catch (e) {
      setError('提交测试失败: ' + e.message);
    } finally {
      setLoading(false);
    }
  }

  async function finishOnboarding() {
    const userId = nickname.trim();
    const mastery = {};
    Object.entries(nodeRatings).forEach(([id, rating]) => {
      mastery[id] = rating;
    });

    // The verification quiz is authoritative for the nodes it tested.
    // Convert the backend's 1–5 score into the 0–1 initialization range.
    quizResults?.results?.forEach(result => {
      if (result.node_id != null && Number.isFinite(result.score)) {
        mastery[result.node_id] = Math.max(0, Math.min(1, (result.score - 1) / 4));
      }
    });

    setLoading(true);
    setError('');
    try {
      await onComplete(userId, mastery);
    } catch (e) {
      setError('初始化失败: ' + e.message);
      setLoading(false);
    }
  }

  function setNodeRating(nodeId, rating) {
    setNodeRatings(prev => ({ ...prev, [nodeId]: rating }));
  }

  function getNodesForChapter(chapterId) {
    return nodes.filter(n => n.chapter_id === chapterId);
  }

  if (loading) return <div className="onboarding"><LoadingSpinner message="加载中..." /></div>;

  return (
    <div className="onboarding">
      <div className="onboarding-card">
        <div className="onboarding-steps">
          <span className={`step-dot ${step >= 1 ? 'active' : ''}`} />
          <span className={`step-dot ${step >= 2 ? 'active' : ''}`} />
          <span className={`step-dot ${step >= 3 ? 'active' : ''}`} />
        </div>

        {error && <div className="onboarding-error">{error}</div>}

        {step === 1 && (
          <div className="onboarding-step">
            <h1>欢迎来到 MathGuide</h1>
            <p className="subtitle">我是你的微积分学习助手，先告诉我你的情况</p>

            <div className="field">
              <label>昵称</label>
              <input
                type="text"
                placeholder="请输入你的昵称"
                value={nickname}
                onChange={e => setNickname(e.target.value)}
                maxLength={20}
                autoFocus
              />
            </div>

            <div className="level-cards">
              {LEVELS.map(l => (
                <button
                  key={l.key}
                  className={`level-card ${level === l.key ? 'selected' : ''}`}
                  onClick={() => setLevel(l.key)}
                >
                  <span className="level-label">{l.label}</span>
                  <span className="level-desc">{l.desc}</span>
                </button>
              ))}
            </div>

            <button
              className="btn-primary"
              disabled={!nicknameValid || !level}
              onClick={handleNext}
            >
              下一步
            </button>
          </div>
        )}

        {step === 2 && (
          <div className="onboarding-step">
            <h2>告诉我你了解哪些知识点</h2>
            <p className="subtitle">标记你对每个知识点的熟悉程度</p>

            <div className="chapters-list">
              {chapters.map(ch => {
                const chNodes = getNodesForChapter(ch.chapter_id);
                const isExpanded = expandedChapter === ch.chapter_id;
                return (
                  <div key={ch.chapter_id} className="chapter-group">
                    <button
                      className="chapter-toggle"
                      onClick={() => setExpandedChapter(isExpanded ? null : ch.chapter_id)}
                    >
                      <span className="chapter-name">{ch.chapter_name}</span>
                      <span className="chapter-count">
                        {chNodes.filter(n => nodeRatings[n.id] !== undefined).length}/{chNodes.length}
                      </span>
                      <span className={`chapter-arrow ${isExpanded ? 'open' : ''}`}>▼</span>
                    </button>
                    {isExpanded && (
                      <div className="node-list">
                        {chNodes.map(node => (
                          <div key={node.id} className="node-row">
                            <span className="node-name">{node.name}</span>
                            <div className="node-btns">
                              {[
                                { label: '不熟悉', value: 0 },
                                { label: '有点印象', value: 0.4 },
                                { label: '掌握良好', value: 0.7 },
                              ].map(opt => (
                                <button
                                  key={opt.value}
                                  className={`node-btn ${nodeRatings[node.id] === opt.value ? 'active' : ''}`}
                                  onClick={() => setNodeRating(node.id, opt.value)}
                                >
                                  {opt.label}
                                </button>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="marked-counter">已标记 {markedCount}/{totalNodes}</div>

            <button className="btn-primary" onClick={handleStart}>
              确认并开始
            </button>
          </div>
        )}

        {step === 3 && (
          <div className="onboarding-step">
            <h2>快速验证</h2>
            <p className="subtitle">
              {quizSubmitted
                ? '验证结果'
                : `回答以下 ${quizQuestions.length} 个问题，验证你的掌握程度`}
            </p>

            {quizSubmitted && quizResults ? (
              <div className="quiz-results">
                <div className="quiz-summary">
                  平均分: {quizResults.summary?.average_score?.toFixed(1) || 'N/A'}
                </div>
                {quizResults.results?.map((r, i) => (
                  <div key={i} className="quiz-result-item">
                    <span className="quiz-result-name">{r.node_name || `题目 ${i + 1}`}</span>
                    <span className="quiz-result-score">得分: {r.score}/5</span>
                    <p className="quiz-result-comment">{r.comment}</p>
                  </div>
                ))}
                <button className="btn-primary" onClick={finishOnboarding}>
                  开始学习
                </button>
              </div>
            ) : quizQuestions.length > 0 ? (
              <div className="quiz-questions">
                {quizQuestions.map((q, i) => (
                  <div key={q.id || i} className="quiz-question">
                    <p className="quiz-q-text">
                      <LatexBlock text={q.text || q.question || ''} />
                    </p>
                    <textarea
                      placeholder="输入你的答案..."
                      value={quizAnswers[q.id] || ''}
                      onChange={e => setQuizAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                      rows={3}
                    />
                  </div>
                ))}
                <button
                  className="btn-primary"
                  onClick={submitQuiz}
                  disabled={quizQuestions.some(q => !quizAnswers[q.id]?.trim())}
                >
                  提交验证
                </button>
                <button className="btn-link" onClick={finishOnboarding}>
                  跳过验证，直接开始
                </button>
              </div>
            ) : (
              <div>
                <p>无法生成测试题</p>
                <button className="btn-primary" onClick={finishOnboarding}>
                  直接开始
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
