import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useUser } from '../context/UserContext';
import { generatePractice, submitPractice, getNode } from '../api/mathguide';
import LatexBlock from '../components/LatexBlock';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';
import mathTrivia from '../data/mathTrivia';
import './StageChallengePage.css';

function storageKey(userId, nodeId) {
  return `mathguide_challenge_${userId}_${nodeId}`;
}

function loadSavedState(userId, nodeId) {
  try {
    const raw = localStorage.getItem(storageKey(userId, nodeId));
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function saveState(userId, nodeId, state) {
  try {
    localStorage.setItem(storageKey(userId, nodeId), JSON.stringify(state));
  } catch { /* quota exceeded */ }
}

function clearSavedState(userId, nodeId) {
  localStorage.removeItem(storageKey(userId, nodeId));
}

export default function StageChallengePage() {
  const { nodeId } = useParams();
  const nodeIdNum = parseInt(nodeId, 10);
  const { userId, refreshMastery } = useUser();
  const navigate = useNavigate();

  const saved = loadSavedState(userId, nodeIdNum);

  const [step, setStep] = useState(() => saved?.step || 'loading');
  const [nodeName, setNodeName] = useState(() => saved?.nodeName || '');
  const [questions, setQuestions] = useState(() => saved?.questions || []);
  const [answers, setAnswers] = useState(() => saved?.answers || {});
  const [results, setResults] = useState(() => saved?.results || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const initializedRef = useRef(false);

  // Persist state on change
  useEffect(() => {
    if (!initializedRef.current) return;
    saveState(userId, nodeIdNum, { step, nodeName, questions, answers, results });
  }, [userId, nodeIdNum, step, nodeName, questions, answers, results]);

  // Load node info and generate questions
  useEffect(() => {
    if (saved && saved.step !== 'loading') {
      initializedRef.current = true;
      return;
    }
    if (initializedRef.current) return;
    initializedRef.current = true;
    initChallenge();
  }, []);

  const initChallenge = async () => {
    setError(null);
    setLoading(true);
    try {
      const nodeData = await getNode(nodeIdNum);
      const name = nodeData?.name || `知识点${nodeIdNum}`;
      setNodeName(name);

      const data = await generatePractice(userId, [nodeIdNum], 2);
      const qs = data.questions || [];
      if (qs.length === 0) {
        setError('题目生成失败，请重试');
        return;
      }
      setQuestions(qs);
      setAnswers({});
      setStep('answer');
    } catch (err) {
      setError('加载挑战失败: ' + err.message);
    } finally {
      setLoading(false);
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
      clearSavedState(userId, nodeIdNum);
    } catch (err) {
      setError('提交失败: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = () => {
    clearSavedState(userId, nodeIdNum);
    setStep('loading');
    setQuestions([]);
    setAnswers({});
    setResults(null);
    initChallenge();
  };

  const handleBackToMap = () => {
    clearSavedState(userId, nodeIdNum);
    navigate('/stages');
  };

  const allAnswered = questions.every((q) => (answers[q.id] || '').trim().length > 0);

  // --- LOADING step ---
  if (step === 'loading') {
    return (
      <div className="challenge-page">
        {error ? (
          <ErrorBanner message={error} onRetry={initChallenge} />
        ) : (
          <LoadingSpinner message="正在生成挑战题目..." trivia={mathTrivia} />
        )}
        <button className="back-link" onClick={handleBackToMap}>返回地图</button>
      </div>
    );
  }

  // --- ANSWER step ---
  if (step === 'answer') {
    return (
      <div className="challenge-page">
        <h2 className="page-title">关卡挑战：{nodeName}</h2>
        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

        <p className="challenge-hint">回答以下 {questions.length} 道题目，检验你对「{nodeName}」的掌握程度。</p>

        <div className="question-list">
          {questions.map((q, idx) => (
            <div key={q.id} className="question-card">
              <div className="question-header">
                <span className="question-num">第 {idx + 1} 题</span>
                <span className={`question-type-badge ${q.type}`}>
                  {q.type === 'conceptual' ? '概念题' : '计算题'}
                </span>
              </div>
              <div className="question-text">
                <LatexBlock content={q.question_text} />
              </div>
              {q.hint && (
                <div className="question-hint"><LatexBlock content={q.hint} /></div>
              )}
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

        <div className="challenge-actions">
          <button className="back-link" onClick={handleBackToMap}>返回地图</button>
          <button
            className="submit-btn"
            onClick={handleSubmit}
            disabled={!allAnswered || loading}
          >
            {loading ? '评估中...' : '提交挑战'}
          </button>
        </div>
      </div>
    );
  }

  // --- RESULTS step ---
  if (step === 'results' && results) {
    const { summary, results: resultItems } = results;
    const cleared = resultItems.every((r) => r.score && r.score >= 3);
    const anyHighScore = resultItems.some((r) => r.score && r.score >= 4);

    return (
      <div className="challenge-page">
        <h2 className="page-title">挑战结果：{nodeName}</h2>

        {cleared && anyHighScore ? (
          <div className="clear-celebration">
            <span className="celebration-icon">&#127881;</span>
            <span className="celebration-text">闯关成功！</span>
          </div>
        ) : (
          <div className="clear-encourage">
            <span className="encourage-icon">&#128170;</span>
            <span className="encourage-text">再接再厉，你可以做得更好！</span>
          </div>
        )}

        <div className="results-summary">
          <div className="summary-card">
            <span className="summary-label">平均分</span>
            <span className="summary-value">{summary.average_score}</span>
          </div>
          <div className="summary-card">
            <span className="summary-label">题数</span>
            <span className="summary-value">{summary.total}</span>
          </div>
        </div>

        <div className="result-list">
          {resultItems.map((r, i) => (
            <div key={i} className={`result-card ${r.score ? 'scored' : 'error'}`}>
              <div className="result-header">
                <span className="result-num">第 {i + 1} 题</span>
                {r.score ? (
                  <span className={`result-score score-${r.score}`}>{r.score} 分</span>
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

        <div className="challenge-actions">
          <button className="back-link" onClick={handleBackToMap}>返回地图</button>
          <button className="submit-btn" onClick={handleRetry}>重新挑战</button>
        </div>
      </div>
    );
  }

  return null;
}
