import { useState, useEffect, useCallback } from 'react';
import { initUser, getRecommendV2, getDimMastery } from './api/mathguide';
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
    setUserId(uid);
    localStorage.setItem(USER_KEY, uid);
    await initUser(uid, { nodeMastery });
    setScreen('main');
  }, []);

  const handleLogoClick = useCallback(() => {
    // 5-tap detection is handled inside the logo element
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
      />
      {devOpen && <DevMode userId={userId} onClose={() => setDevOpen(false)} />}
    </div>
  );
}
