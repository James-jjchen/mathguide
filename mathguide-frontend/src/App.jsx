import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { UserProvider, useUser } from './context/UserContext';
import Header from './components/Header';
import WelcomePage from './pages/WelcomePage';
import ChatPage from './pages/ChatPage';
import PracticePage from './pages/PracticePage';
import DashboardPage from './pages/DashboardPage';
import StageMapPage from './pages/StageMapPage';
import StageChallengePage from './pages/StageChallengePage';
import AdminPage from './pages/AdminPage';
import './App.css';

function ProtectedRoute({ children }) {
  const { initialized } = useUser();
  if (!initialized) return <Navigate to="/" replace />;
  return children;
}

function AdminRoute({ children }) {
  const { initialized, isAdmin } = useUser();
  if (!initialized) return <Navigate to="/" replace />;
  if (!isAdmin) return <Navigate to="/chat" replace />;
  return children;
}

function AppRoutes() {
  const { initialized } = useUser();

  return (
    <Routes>
      <Route
        path="/"
        element={
          initialized ? <Navigate to="/chat" replace /> : <WelcomePage />
        }
      />
      <Route
        path="/chat"
        element={
          <ProtectedRoute>
            <ChatPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/practice"
        element={
          <ProtectedRoute>
            <PracticePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/stages"
        element={
          <ProtectedRoute>
            <StageMapPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/stages/node/:nodeId"
        element={
          <ProtectedRoute>
            <StageChallengePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin"
        element={
          <AdminRoute>
            <AdminPage />
          </AdminRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <UserProvider>
        <div className="app-shell">
          <Header />
          <AppRoutes />
        </div>
      </UserProvider>
    </BrowserRouter>
  );
}
