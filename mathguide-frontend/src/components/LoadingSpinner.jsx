import { useState, useEffect } from 'react';
import './LoadingSpinner.css';

export default function LoadingSpinner({ message = '加载中...', trivia = null }) {
  const [triviaIndex, setTriviaIndex] = useState(() =>
    trivia && trivia.length > 0 ? Math.floor(Math.random() * trivia.length) : 0
  );

  useEffect(() => {
    if (!trivia || trivia.length === 0) return;
    const timer = setInterval(() => {
      setTriviaIndex((prev) => {
        let next;
        do { next = Math.floor(Math.random() * trivia.length); }
        while (next === prev && trivia.length > 1);
        return next;
      });
    }, 30000);
    return () => clearInterval(timer);
  }, [trivia]);

  const currentTrivia = trivia && trivia.length > 0 ? trivia[triviaIndex] : null;

  return (
    <div className="spinner-container">
      <div className="spinner" />
      <p className="spinner-message">{message}</p>
      {currentTrivia && (
        <p className="spinner-trivia">
          <span className="trivia-label">你知道吗：</span>
          {currentTrivia}
        </p>
      )}
    </div>
  );
}
