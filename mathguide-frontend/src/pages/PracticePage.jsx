import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser } from '../context/UserContext';
import { diagnoseWeaknesses, generatePractice, submitPractice } from '../api/mathguide';
import LatexBlock from '../components/LatexBlock';
import MasteryBar from '../components/MasteryBar';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';
import EmptyState from '../components/EmptyState';
import mathTrivia from '../data/mathTrivia';
import './PracticePage.css';

const PRACTICE_STORAGE_KEY = 'mathguide_practice_state';

// Steps:
// 'select' -> choose weak nodes
// 'answer' -> answer generated questions
// 'results' -> show evaluation results

function loadSavedState(userId) {
  try {
    const raw = localStorage.getItem(PRACTICE_STORAGE_KEY);
    if (!raw) return null;
    const saved = JSON.parse(raw);
    if (saved.userId !== userId) return null;
    return saved;
  } catch {
    return null;
  }
}

function saveState(userId, state) {
  try {
    localStorage.setItem(PRACTICE_STORAGE_KEY, JSON.stringify({ userId, ...state }));
  } catch { /* quota exceeded, ignore */ }
}

function clearSavedState() {
  localStorage.removeItem(PRACTICE_STORAGE_KEY);
}

export default function PracticePage() {
  const { userId, refreshMastery } = useUser();
  const navigate = useNavigate();

  const saved = loadSavedState(userId);

  const [step, setStep] = useState(() => saved?.step || 'select');
  const [weaknesses, setWeaknesses] = useState(() => saved?.weaknesses || []);
  const [selectedIds, setSelectedIds] = useState(() => saved?.selectedIds || []);
  const [questions, setQuestions] = useState(() => saved?.questions || []);
  const [answers, setAnswers] = useState(() => saved?.answers || {});
  const [results, setResults] = useState(() => saved?.results || null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  const initializedRef = useRef(false);

  // Persist practice state to localStorage on every change
  useEffect(() => {
    if (!initializedRef.current) return;
    saveState(userId, { step, weaknesses, selectedIds, questions, answers, results });
  }, [userId, step, weaknesses, selectedIds, questions, answers, results]);

  // Load weaknesses on mount (only if no saved state)
  useEffect(() => {
    if (saved && saved.step !== 'select') {
      initializedRef.current = true;
      return;
    }
    if (initializedRef.current) return;
    initializedRef.current = true;
    loadWeaknesses();
  }, []);

  const loadWeaknesses = async () => {
    setError(null);
    setLoading(true);
    try {
      const data = await diagnoseWeaknesses(userId);
      setWeaknesses(data.weaknesses || []);
      if (data.message) {
        setError(data.message);
      }
    } catch (err) {
      setError('加载薄弱点失败: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleNode = (nodeId) => {
    setSelectedIds((prev) =>
      prev.includes(nodeId) ? prev.filter((id) => id !== nodeId) : [...prev, nodeId]
    );
  };

  const handleGenerate = async () => {
    if (selectedIds.length === 0) return;
    setError(null);
    setGenerating(true);
    try {
      const data = await generatePractice(userId, selectedIds, selectedIds.length * 2);
      setQuestions(data.questions || []);
      setAnswers({});
      if (data.questions && data.questions.length > 0) {
        setStep('answer');
      } else {
        setError('生成练习题失败，请重试');
      }
    } catch (err) {
      setError('生成练习题失败: ' + err.message);
    } finally {
      setGenerating(false);
    }
  };

  const updateAnswer = (questionId, value) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  };

  const handleSubmit = async () => {
    const answersList = questions.map((q) => ({
      question_id: q.id,
      node_id: q.node_id,
      question_text: q.question_text,
      student_answer: answers[q.id] || '',
    }));

    setError(null);
    setLoading(true);
    try {
      const data = await submitPractice(userId, answersList);
      setResults(data);
      setStep('results');
      await refreshMastery();
    } catch (err) {
      setError('提交失败: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = () => {
    clearSavedState();
    setStep('select');
    setQuestions([]);
    setAnswers({});
    setResults(null);
    setSelectedIds([]);
    loadWeaknesses();
  };

  const allAnswered = questions.every((q) => (answers[q.id] || '').trim().length > 0);

  // --- SELECT step ---
  if (step === 'select') {
    return (
      <div className="practice-page">
        <h2 className="page-title">练习模式</h2>
        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} onRetry={loadWeaknesses} />}

        {generating ? (
          <LoadingSpinner message="正在生成练习题..." trivia={mathTrivia} />
        ) : loading ? (
          <LoadingSpinner message="加载薄弱知识点..." />
        ) : weaknesses.length === 0 ? (
          <EmptyState
            icon="&#127881;"
            title="暂无薄弱知识点！"
            description="你已经掌握了所有内容，继续保持！可以返回聊天继续提问。"
          />
        ) : (
          <>
            <p className="practice-hint">选择你想要练习的知识点，系统将生成针对性练习题</p>
            <div className="node-select-list">
              {weaknesses.map((w) => (
                <label key={w.node_id} className={`node-select-item ${selectedIds.includes(w.node_id) ? 'selected' : ''}`}>
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(w.node_id)}
                    onChange={() => toggleNode(w.node_id)}
                  />
                  <div className="node-select-info">
                    <span className="node-select-name">{w.name}</span>
                    <MasteryBar nodeId={w.node_id} nodeName="" mastery={w.mastery} compact />
                    <span className={`priority-tag ${w.priority}`}>
                      {w.priority === 'high' ? '急需复习' : w.priority === 'medium' ? '需要加强' : '稍弱'}
                    </span>
                  </div>
                </label>
              ))}
            </div>
            <button
              className="generate-btn"
              onClick={handleGenerate}
              disabled={selectedIds.length === 0 || generating}
            >
              生成练习题 ({selectedIds.length}个知识点)
            </button>
          </>
        )}

        <button className="back-link" onClick={() => navigate('/chat')}>返回聊天</button>
      </div>
    );
  }

  // --- ANSWER step ---
  if (step === 'answer') {
    return (
      <div className="practice-page">
        <h2 className="page-title">回答练习题</h2>
        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

        <div className="question-list">
          {questions.map((q) => (
            <div key={q.id} className="question-card">
              <div className="question-header">
                <span className="question-node">{q.node_name}</span>
                <span className={`question-type ${q.type}`}>
                  {q.type === 'conceptual' ? '概念题' : '计算题'}
                </span>
              </div>
              <div className="question-text">
                <LatexBlock content={q.question_text} />
              </div>
              {q.hint && <div className="question-hint"><LatexBlock content={q.hint} /></div>}
              <textarea
                className="answer-textarea"
                placeholder="输入你的回答..."
                value={answers[q.id] || ''}
                onChange={(e) => updateAnswer(q.id, e.target.value)}
                rows={3}
              />
            </div>
          ))}
        </div>

        <div className="answer-actions">
          <button className="back-link" onClick={() => setStep('select')}>重新选择</button>
          <button
            className="submit-btn"
            onClick={handleSubmit}
            disabled={!allAnswered || loading}
          >
            {loading ? '提交中...' : '提交答案'}
          </button>
        </div>
      </div>
    );
  }

  // --- RESULTS step ---
  if (step === 'results' && results) {
    const { summary } = results;
    return (
      <div className="practice-page">
        <h2 className="page-title">练习结果</h2>

        <div className="results-summary">
          <div className="summary-card">
            <span className="summary-label">平均分</span>
            <span className="summary-value">{summary.average_score}</span>
          </div>
          <div className="summary-card">
            <span className="summary-label">总题数</span>
            <span className="summary-value">{summary.total}</span>
          </div>
          <div className="summary-card">
            <span className="summary-label">得分分布</span>
            <div className="score-dist">
              {[5, 4, 3, 2, 1].map((s) => (
                <span key={s} className="dist-item">
                  {s}分: {summary.score_breakdown[s] || 0}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="result-list">
          {results.results.map((r, i) => (
            <div key={i} className={`result-card ${r.score ? 'scored' : 'error'}`}>
              <div className="result-header">
                <span className="result-node">{r.node_name}</span>
                {r.score ? (
                  <span className={`result-score score-${r.score}`}>{r.score}分</span>
                ) : (
                  <span className="result-error-tag">评估失败</span>
                )}
              </div>
              {r.comment && <p className="result-comment">{r.comment}</p>}
              <div className="result-mastery">
                <span>掌握度: {r.mastery_before} → {r.mastery_after}</span>
                <span className={`mastery-change ${r.mastery_after >= r.mastery_before ? 'up' : 'down'}`}>
                  {r.mastery_after >= r.mastery_before ? '+' : ''}
                  {(r.mastery_after - r.mastery_before).toFixed(2)}
                </span>
              </div>
            </div>
          ))}
        </div>

        <div className="result-actions">
          <button className="back-link" onClick={handleRetry}>继续练习</button>
          <button className="submit-btn" onClick={() => navigate('/chat')}>返回聊天</button>
        </div>
      </div>
    );
  }

  return null;
}
