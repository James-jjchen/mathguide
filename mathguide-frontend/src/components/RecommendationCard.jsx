import { useState, useEffect } from 'react';
import { getProblemForDim } from '../api/mathguide';
import LatexBlock from './LatexBlock';
import './RecommendationCard.css';

const TYPE_ICONS = {
  bottleneck: '🔴',
  unlock: '🟢',
  transfer: '🟡',
  discovery: '🟣',
  recovery: '🔵',
};

const TYPE_LABELS = {
  bottleneck: '瓶颈突破',
  unlock: '即将解锁',
  transfer: '横向转移',
  discovery: '探索发现',
  recovery: '动量恢复',
};

export default function RecommendationCard({ recommendation, onPractice, onAskAI }) {
  const { action_type, target_dim_name, explanation, score, affected_dims } = recommendation;
  const icon = TYPE_ICONS[action_type] || '📌';
  const label = TYPE_LABELS[action_type] || '推荐';

  return (
    <div className="rec-card">
      <div className="rec-card-header">
        <span className="rec-type-badge" data-type={action_type}>
          {icon} {label}
        </span>
        <span className="rec-score">
          推荐度: {(score * 100).toFixed(0)}%
        </span>
      </div>

      <h3 className="rec-dim-name">{target_dim_name}</h3>
      <p className="rec-explanation">{explanation}</p>

      {affected_dims && affected_dims.length > 0 && (
        <div className="rec-affected">
          {affected_dims.map(d => (
            <span key={d} className="affected-tag">{d}</span>
          ))}
        </div>
      )}

      <div className="rec-actions">
        <button className="rec-btn practice-btn" onClick={onPractice}>
          ✏️ 做题
        </button>
        <button className="rec-btn ask-btn" onClick={onAskAI}>
          💬 问 AI
        </button>
      </div>
    </div>
  );
}
