import { useState, useCallback } from 'react';
import { initUser } from './api/mathguide';
import Onboarding from './components/Onboarding';
import MainLayout from './components/MainLayout';
import DevMode from './components/DevMode';
import './App.css';

const USER_KEY = 'mathguide_userId';

export default function App() {
  const [screen, setScreen] = useState(() => {
    return localStorage.getItem(USER_KEY) ? 'main' : 'onboarding';
  });
  const [userId, setUserId] = useState(() => localStorage.getItem(USER_KEY) || '');
  const [devOpen, setDevOpen] = useState(false);

  const handleOnboardingComplete = useCallback(async (uid, nodeMastery) => {
    await initUser(uid, { nodeMastery });
    setUserId(uid);
    localStorage.setItem(USER_KEY, uid);
    setScreen('main');
  }, []);

  const handleLogout = useCallback(() => {
    localStorage.removeItem(USER_KEY);
    setUserId('');
    setDevOpen(false);
    setScreen('onboarding');
  }, []);

  if (screen === 'onboarding') {
    return (
      <div className="app-shell">
        <Onboarding onComplete={handleOnboardingComplete} />
      </div>
    );
  }

  return (
    <div className="app-shell">
      <MainLayout
        userId={userId}
        onLogoActivate={() => setDevOpen(true)}
        onLogout={handleLogout}
      />
      {devOpen && <DevMode userId={userId} onClose={() => setDevOpen(false)} />}
    </div>
  );
}
