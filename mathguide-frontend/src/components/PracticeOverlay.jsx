import { useState, useCallback, useMemo } from 'react';
import LatexBlock from './LatexBlock';
import './PracticeOverlay.css';

export default function PracticeOverlay({ problem, dimId, dimName, onComplete, onClose, onAskAI }) {
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedChoice, setSelectedChoice] = useState(null);
  const [showResult, setShowResult] = useState(false);
  const [stepResults, setStepResults] = useState([]); // { stepId, correct, selected }
  const [finished, setFinished] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');

  const steps = useMemo(() => problem?.steps || [], [problem]);
  const step = steps[currentStep];
  const totalSteps = steps.length;
  const allCorrect = stepResults.every(r => r.correct);
  const correctCount = stepResults.filter(r => r.correct).length;

  const handleChoice = useCallback((idx) => {
    if (showResult) return;
    setSelectedChoice(idx);
    setShowResult(true);

    const isCorrect = idx === step.correct;
    setStepResults(prev => [...prev, {
      stepId: step.id,
      dimId: step.dim_id || dimId,
      correct: isCorrect,
      selected: idx,
    }]);
  }, [showResult, step, dimId]);

  const handleNext = useCallback(() => {
    if (currentStep + 1 >= totalSteps) {
      setFinished(true);
    } else {
      setCurrentStep(prev => prev + 1);
      setSelectedChoice(null);
      setShowResult(false);
    }
  }, [currentStep, totalSteps]);

  const handleComplete = useCallback(async () => {
    const answers = stepResults.map((r, i) => ({
      question_id: `${problem.id}_${r.stepId}`,
      dim_id: r.dimId,
      node_id: steps[i]?.node_id ?? null,
      outcome: r.correct ? 'correct' : 'wrong',
      question_text: steps[i]?.text || '',
      student_answer: `选择了: ${steps[i]?.choices?.[r.selected] || ''}`,
    }));
    setSubmitting(true);
    setSubmitError('');
    try {
      await onComplete(answers);
    } catch (error) {
      setSubmitError(`提交失败：${error.message}`);
      setSubmitting(false);
    }
  }, [stepResults, problem, steps, onComplete]);

  if (finished) {
    return (
      <div className="practice-overlay">
        <div className="practice-modal">
          <div className="practice-result">
            <div className="result-icon">{allCorrect ? '✓' : '✗'}</div>
            <h2>{allCorrect ? '全对！' : '练习完成'}</h2>
            <p className="result-summary">
              正确 {correctCount}/{totalSteps} 步
            </p>
            <div className="result-steps">
              {stepResults.map((r, i) => (
                <div key={i} className={`result-step ${r.correct ? 'correct' : 'wrong'}`}>
                  <span>{r.correct ? '✓' : '✗'}</span>
                  <span>第 {i + 1} 步</span>
                </div>
              ))}
            </div>
            <div className="result-actions">
              {submitError && <p className="practice-submit-error">{submitError}</p>}
              <button className="btn-primary" onClick={handleComplete} disabled={submitting}>
                {submitting ? '正在保存...' : submitError ? '重试提交' : '保存并返回推荐'}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!step) {
    return (
      <div className="practice-overlay">
        <div className="practice-modal">
          <p>该题目没有解题步骤</p>
          <button className="btn-primary" onClick={onClose}>返回</button>
        </div>
      </div>
    );
  }

  const correctChoice = step.choices?.[step.correct] || '';

  return (
    <div className="practice-overlay">
      <div className="practice-modal">
        <div className="practice-header">
          <span className="practice-title">{dimName} · 第 {currentStep + 1}/{totalSteps} 步</span>
          <button className="practice-close" onClick={onClose}>×</button>
        </div>

        <div className="practice-problem">
          <LatexBlock text={problem.text} />
        </div>

        <div className="practice-step">
          <p className="step-question">{step.text}</p>

          <div className="step-choices">
            {step.choices?.map((choice, idx) => (
              <button
                key={idx}
                className={`choice-btn ${
                  showResult
                    ? idx === step.correct
                      ? 'correct'
                      : idx === selectedChoice
                      ? 'wrong'
                      : 'dimmed'
                    : selectedChoice === idx
                    ? 'selected'
                    : ''
                }`}
                onClick={() => handleChoice(idx)}
                disabled={showResult}
              >
                {choice}
              </button>
            ))}
          </div>
        </div>

        {showResult && selectedChoice !== step.correct && (
          <div className="wrong-explanation">
            <p className="wrong-label">✗ 答错了</p>
            <p className="wrong-chosen">你选了"{step.choices?.[selectedChoice]}"</p>
            <p className="wrong-correct">正确做法: {correctChoice}</p>
            <div className="wrong-actions">
              <button className="btn-primary" onClick={handleNext}>
                我懂了，继续
              </button>
              <button className="btn-ask" onClick={onAskAI}>
                问 AI
              </button>
            </div>
          </div>
        )}

        {showResult && selectedChoice === step.correct && (
          <div className="correct-feedback">
            <p className="correct-label">✓ 正确!</p>
            <button className="btn-primary" onClick={handleNext}>
              {currentStep + 1 >= totalSteps ? '查看结果' : '继续'}
            </button>
          </div>
        )}

        {!showResult && (
          <div className="practice-footer">
            <button
              className="btn-primary"
              disabled={selectedChoice === null}
              onClick={() => selectedChoice !== null && handleChoice(selectedChoice)}
            >
              确认
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
