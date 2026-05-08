import { useState, useEffect } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useUser } from '../context/UserContext';
import AdminLoginModal from './AdminLoginModal';
import './Header.css';

export default function Header() {
  const { userId, initialized, reset, isAdmin, logoutAdmin } = useUser();
  const [devOpen, setDevOpen] = useState(false);
  const [showAdminModal, setShowAdminModal] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (!devOpen) return;
    const handler = (e) => {
      if (!e.target.closest('.dev-menu')) setDevOpen(false);
    };
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [devOpen]);

  if (!initialized) return null;

  return (
    <header className="app-header">
      <div className="header-brand">MathGuide</div>
      <nav className="header-nav">
        <NavLink to="/chat" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          问答
        </NavLink>
        <NavLink to="/practice" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          练习
        </NavLink>
        <NavLink to="/stages" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          闯关
        </NavLink>
      </nav>

      <div className="header-user">
        <div className="dev-menu">
          <button
            className={`dev-trigger${devOpen ? ' open' : ''}${isAdmin ? ' admin-active' : ''}`}
            onClick={(e) => { e.stopPropagation(); setDevOpen((v) => !v); }}
            title="用户选项"
          >
            {isAdmin ? '👑 ' : ''}{userId}
            <span className="dev-arrow">▾</span>
          </button>

          {devOpen && (
            <div className="dev-dropdown">
              <button
                className="dev-menu-item"
                onClick={() => { setDevOpen(false); navigate('/profile'); }}
              >
                个人数据
              </button>
              {isAdmin && (
                <button
                  className="dev-menu-item"
                  onClick={() => { setDevOpen(false); navigate('/admin'); }}
                >
                  管理面板
                </button>
              )}
              <div className="dev-dropdown-divider" />
              {isAdmin ? (
                <button
                  className="dev-menu-item"
                  onClick={() => { setDevOpen(false); logoutAdmin(); }}
                >
                  退出管理员模式
                </button>
              ) : (
                <button
                  className="dev-menu-item"
                  onClick={() => { setDevOpen(false); setShowAdminModal(true); }}
                >
                  启用管理员模式
                </button>
              )}
            </div>
          )}
        </div>

        <button className="logout-btn" onClick={reset} title="退出">退出</button>
      </div>

      {showAdminModal && <AdminLoginModal onClose={() => setShowAdminModal(false)} />}
    </header>
  );
}
