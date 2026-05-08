import { useState, useRef, useEffect } from 'react';
import { useUser } from '../context/UserContext';
import './AdminLoginModal.css';

export default function AdminLoginModal({ onClose }) {
  const { loginAdmin } = useUser();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const usernameRef = useRef(null);

  useEffect(() => { usernameRef.current?.focus(); }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError('请输入管理员用户名和密码');
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await loginAdmin(username.trim(), password);
      onClose();
    } catch (err) {
      setError(err.message || '认证失败');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="admin-modal-overlay" onClick={onClose}>
      <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
        <h2 className="admin-modal-title">管理员认证</h2>
        <form onSubmit={handleSubmit}>
          {error && <div className="admin-modal-error">{error}</div>}
          <label className="admin-modal-label">管理员用户名</label>
          <input
            ref={usernameRef}
            className="admin-modal-input"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="输入管理员用户名"
            disabled={busy}
            autoComplete="username"
          />
          <label className="admin-modal-label">管理员密码</label>
          <input
            className="admin-modal-input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="输入管理员密码"
            disabled={busy}
            autoComplete="current-password"
          />
          <div className="admin-modal-actions">
            <button type="button" className="admin-modal-btn cancel" onClick={onClose} disabled={busy}>
              取消
            </button>
            <button type="submit" className="admin-modal-btn confirm" disabled={busy}>
              {busy ? '验证中...' : '确认'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
