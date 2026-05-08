import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser } from '../context/UserContext';
import { initUser, getMastery, generatePractice, submitPractice } from '../api/mathguide';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';
import LatexBlock from '../components/LatexBlock';
import mathTrivia from '../data/mathTrivia';
import './WelcomePage.css';

const LEVELS = [
  { cls: 'cf-low', label: '不熟悉', mastery: 0.0 },
  { cls: 'cf-mid', label: '有点印象', mastery: 0.4 },
  { cls: 'cf-high', label: '掌握良好', mastery: 0.7 },
];

const EXPERIENCE_OPTIONS = [
  { value: 'beginner', label: '我是初学者', desc: '第一次系统学习微积分，从零开始' },
  { value: 'some', label: '我学过一些', desc: '了解部分概念，想查漏补缺' },
  { value: 'review', label: '我想巩固复习', desc: '已系统学过，需要复习和强化' },
];

export default function WelcomePage() {
  const { userId, setUserId, chapters, nodes, setInitialized, setMastery, initialized } = useUser();
  const [step, setStep] = useState(1);
  const [nickname, setNickname] = useState(userId || '');
  const [level, setLevel] = useState('some');
  const [cf, setCf] = useState({});
  const [open, setOpen] = useState({});
  const [quiz, setQuiz] = useState([]);
  const [answers, setAnswers] = useState({});
  const [quizBusy, setQuizBusy] = useState(false);
  const [quizDone, setQuizDone] = useState(false);
  const [quizResult, setQuizResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const nav = useNavigate();

  if (initialized) { nav('/chat', { replace: true }); return null; }

  const byChapter = useMemo(() => {
    const m = {};
    for (const ch of chapters) {
      m[ch.chapter_id] = {
        name: ch.chapter_name,
        nodes: nodes.filter(n => n.chapter_id === ch.chapter_id)
      };
    }
    return m;
  }, [chapters, nodes]);

  const stats = useMemo(() => {
    let hi = 0, mi = 0;
    for (const v of Object.values(cf)) {
      if (v === 2) hi++; else if (v === 1) mi++;
    }
    return { hi, mi, lo: nodes.length - hi - mi, total: nodes.length };
  }, [cf, nodes.length]);

  const chSummary = useMemo(() => {
    const s = {};
    for (const [id, d] of Object.entries(byChapter)) {
      const ids = d.nodes.map(n => n.id);
      s[id] = { hi: ids.filter(i => cf[i] === 2).length, mi: ids.filter(i => cf[i] === 1).length };
    }
    return s;
  }, [byChapter, cf]);

  const name = nickname.trim();

  function initCf() {
    if (Object.keys(cf).length > 0) return;
    const d = {}; for (const n of nodes) d[n.id] = 0;
    setCf(d);
    const o = {}; for (const ch of chapters) o[ch.chapter_id] = true;
    setOpen(o);
  }

  function setNode(nid, lv) { setCf(p => ({ ...p, [nid]: lv })); }

  function setChapter(cid, lv) {
    const ns = byChapter[cid]?.nodes || [];
    setCf(p => { const n = { ...p }; for (const nd of ns) n[nd.id] = lv; return n; });
  }

  function toggle(cid) { setOpen(p => ({ ...p, [cid]: !p[cid] })); }

  function buildMastery() {
    const m = {};
    for (const [nid, lv] of Object.entries(cf)) m[parseInt(nid)] = LEVELS[lv].mastery;
    return m;
  }

  async function doInit(override) {
    const m = override || buildMastery();
    await initUser(name, { nodeMastery: m });
    setUserId(name);
    const d = await getMastery(name);
    setMastery(d.mastery || {});
    setInitialized(true);
    nav('/chat');
  }

  async function goBeginner() {
    if (!name) { setErr('请输入用户名'); return; }
    setErr(null); setBusy(true);
    try {
      await initUser(name, {});
      setUserId(name);
      const d = await getMastery(name);
      setMastery(d.mastery || {});
      setInitialized(true);
      nav('/chat');
    } catch (e) { setErr('初始化失败: ' + e.message); } finally { setBusy(false); }
  }

  function goNext() {
    if (!name) { setErr('请输入用户名'); return; }
    setErr(null);
    if (level === 'beginner') { goBeginner(); return; }
    initCf();
    setStep(2);
  }

  function goFromSurvey() {
    const hi = Object.entries(cf).filter(([, v]) => v === 2).map(([k]) => parseInt(k));
    if (hi.length === 0) { goFinish(); } else { setStep(3); }
  }

  async function goFinish() {
    setBusy(true); setErr(null);
    try { await doInit(); } catch (e) { setErr('初始化失败: ' + e.message); setBusy(false); }
  }

  async function goQuiz() {
    setQuizBusy(true); setErr(null);
    try {
      const hi = Object.entries(cf).filter(([, v]) => v === 2).map(([k]) => parseInt(k));
      const ids = [];
      for (const [, d] of Object.entries(byChapter)) {
        const inCh = d.nodes.filter(n => hi.includes(n.id));
        if (inCh.length > 0) ids.push(inCh[0].id);
      }
      const r = await generatePractice(name, ids, ids.length);
      setQuiz(r.questions || []);
      const a = {}; for (const q of r.questions || []) a[q.id] = '';
      setAnswers(a);
    } catch (e) { setErr('生成题目失败: ' + e.message); } finally { setQuizBusy(false); }
  }

  async function goSubmit() {
    setBusy(true); setErr(null);
    try {
      await initUser(name, { nodeMastery: buildMastery() });
      setUserId(name);
      const body = quiz.map(q => ({
        question_id: q.id, node_id: q.node_id,
        question_text: q.question_text,
        student_answer: answers[q.id] || '',
      }));
      const r = await submitPractice(name, body);
      setQuizResult(r); setQuizDone(true);
      const d = await getMastery(name);
      setMastery(d.mastery || {});
      setInitialized(true);
      nav('/chat');
    } catch (e) { setErr('提交失败: ' + e.message); setBusy(false); }
  }

  return (
    <div className="wp">
      <div className={`wp-card${step === 2 ? ' wp-wide' : ''}`}>
        <h1 className="wp-title">MathGuide</h1>
        <p className="wp-sub">智能微积分学习助手</p>

        <div className="wp-dots">
          {[1, 2, 3].map(s => <span key={s} className={`wp-dot${s === step ? ' on' : s < step ? ' done' : ''}`} />)}
        </div>

        {err && <ErrorBanner message={err} onDismiss={() => setErr(null)} />}

        {/* ============ STEP 1 ============ */}
        {step === 1 && (
          <div className="wp-form">
            <p className="wp-desc">基于知识图谱的大学微积分辅导系统，通过智能问答诊断你的薄弱点，生成针对性练习</p>
            <label className="wp-label">你的昵称</label>
            <input className="wp-input" type="text" value={nickname}
              onChange={e => setNickname(e.target.value)} placeholder="输入昵称..." disabled={busy} />
            <label className="wp-label">你的学习阶段</label>
            <div className="wp-exp-options">
              {EXPERIENCE_OPTIONS.map(o => (
                <button key={o.value} className={`wp-exp-card${level === o.value ? ' sel' : ''}`}
                  onClick={() => setLevel(o.value)} disabled={busy}>
                  <span className="wp-exp-label">{o.label}</span>
                  <span className="wp-exp-desc">{o.desc}</span>
                </button>
              ))}
            </div>
            <button className="wp-btn" onClick={goNext} disabled={busy}>
              {level === 'beginner' ? '开始学习' : '下一步'}
            </button>
          </div>
        )}

        {/* ============ STEP 2 ============ */}
        {step === 2 && (
          <div className="wp-form">
            <p className="wp-survey-hint">请标记你对以下知识点的熟悉程度，帮助我们为你定制学习路径</p>

            <div className="wp-survey-bar">
              已标记 <b>{stats.hi + stats.mi}</b> / {stats.total} 个知识点
              <span className="wp-survey-legend">
                <i className="wp-ldot hi" /> 掌握良好
                <i className="wp-ldot mi" /> 有点印象
                <i className="wp-ldot lo" /> 不熟悉
              </span>
            </div>

            <div className="wp-ch-list">
              {Object.entries(byChapter).map(([cid, d]) => (
                <div key={cid} className="wp-ch">
                  <div className="wp-ch-head" onClick={() => toggle(cid)}>
                    <span className="wp-ch-arrow">{open[cid] ? '▾' : '▸'}</span>
                    <span className="wp-ch-name">{d.name}</span>
                    {chSummary[cid]?.hi > 0 && <span className="wp-ch-tag hi">{chSummary[cid].hi} 掌握</span>}
                    {chSummary[cid]?.mi > 0 && <span className="wp-ch-tag mi">{chSummary[cid].mi} 印象</span>}
                    <span className="wp-ch-spacer" />
                    <button className="wp-ch-batch" onClick={e => { e.stopPropagation(); setChapter(+cid, 2); }}>全选</button>
                    <button className="wp-ch-batch" onClick={e => { e.stopPropagation(); setChapter(+cid, 0); }}>清除</button>
                  </div>
                  {open[cid] && (
                    <div className="wp-ch-body">
                      {d.nodes.map(n => (
                        <div key={n.id} className="wp-row">
                          <span className="wp-row-name">{n.name}</span>
                          <span className="wp-row-toggle">
                            {LEVELS.map((lv, i) => (
                              <button key={i}
                                className={`wp-cf-btn ${lv.cls}${cf[n.id] === i ? ' on' : ''}`}
                                onClick={() => setNode(n.id, i)}>
                                {lv.label}
                              </button>
                            ))}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="wp-actions">
              <button className="wp-btn-back" onClick={() => setStep(1)}>返回</button>
              <button className="wp-btn" onClick={goFromSurvey}>下一步</button>
            </div>
          </div>
        )}

        {/* ============ STEP 3 ============ */}
        {step === 3 && (
          <div className="wp-form">
            <p className="wp-survey-hint">复习建议</p>
            <div className="wp-quiz-summary">
              <p>你标记了 <b>{stats.hi}</b> 个「掌握良好」和 <b>{stats.mi}</b> 个「有点印象」的知识点。</p>
              {stats.hi > 0 && <p className="wp-quiz-note">建议花1-2分钟快速验证一下掌握良好的知识点，帮助系统更准确地评估你的水平。</p>}
            </div>

            {quiz.length === 0 && !quizBusy && (
              <div className="wp-actions">
                <button className="wp-btn-back" onClick={() => setStep(2)}>返回修改</button>
                <button className="wp-btn-skip" onClick={goQuiz} disabled={stats.hi === 0}>快速验证（推荐）</button>
                <button className="wp-btn" onClick={goFinish} disabled={busy}>
                  {busy ? <LoadingSpinner /> : '跳过，直接开始'}
                </button>
              </div>
            )}

            {quizBusy && <LoadingSpinner message="正在生成验证题目..." trivia={mathTrivia} />}

            {quiz.length > 0 && !quizDone && (
              <div>
                {quiz.map((q, i) => (
                  <div key={q.id} className="wp-quiz-card">
                    <p className="wp-quiz-num">第 {i + 1} 题 — {q.node_name}</p>
                    <LatexBlock content={q.question_text} />
                    {q.hint && <div className="wp-quiz-hint"><LatexBlock content={q.hint} /></div>}
                    <textarea className="wp-quiz-input" value={answers[q.id] || ''}
                      onChange={e => setAnswers(p => ({ ...p, [q.id]: e.target.value }))}
                      placeholder="输入你的答案..." rows={3} disabled={busy} />
                  </div>
                ))}
                {quizResult && (
                  <div className="wp-quiz-results">
                    {quizResult.results?.map(r => (
                      <div key={r.question_id} className="wp-quiz-r-item">
                        <span>{r.node_name}: </span>
                        <span className={`wp-quiz-score s${r.score}`}>{r.score !== null ? `${r.score}/5` : '评估失败'}</span>
                        {r.comment && <p className="wp-quiz-comment">{r.comment}</p>}
                      </div>
                    ))}
                  </div>
                )}
                <div className="wp-actions">
                  <button className="wp-btn-back" onClick={() => { setQuiz([]); setAnswers({}); }} disabled={busy}>返回</button>
                  <button className="wp-btn" onClick={goSubmit}
                    disabled={busy || Object.values(answers).some(a => !(a || '').trim())}>
                    {busy ? '提交中...' : '提交并开始学习'}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
