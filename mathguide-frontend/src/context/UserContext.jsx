import { createContext, useContext, useState, useCallback, useEffect, useMemo } from 'react';
import { getMastery, getNodes, getChapters, adminLogin as apiAdminLogin } from '../api/mathguide';

const UserContext = createContext(null);

function makeConv(id) {
  return { id, title: '新对话', messages: [], createdAt: Date.now() };
}

function convKey(uid) { return `mathguide_convs_${uid}`; }
function activeKey(uid) { return `mathguide_active_${uid}`; }

function loadConvs(uid) {
  if (!uid) return null;
  try {
    const raw = localStorage.getItem(convKey(uid));
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function saveConvs(uid, convs) {
  if (!uid) return;
  try { localStorage.setItem(convKey(uid), JSON.stringify(convs)); } catch {}
}

function defaultConvs() {
  const c = makeConv('1');
  return { [c.id]: c };
}

export function UserProvider({ children }) {
  const [userId, setUserIdState] = useState(() => localStorage.getItem('mathguide_userId') || '');
  const [initialized, setInitialized] = useState(false);
  const [nodes, setNodes] = useState([]);
  const [chapters, setChapters] = useState([]);
  const [mastery, setMastery] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [adminToken, setAdminToken] = useState(null);
  const isAdmin = !!adminToken;

  // --- Conversations (user-scoped) ---
  const [conversations, setConversations] = useState(() => {
    const uid = localStorage.getItem('mathguide_userId') || '';
    const saved = loadConvs(uid);
    if (saved && Object.keys(saved).length > 0) return saved;
    return defaultConvs();
  });

  const [activeConvId, setActiveConvId] = useState(() => {
    const uid = localStorage.getItem('mathguide_userId') || '';
    return localStorage.getItem(activeKey(uid)) || '1';
  });

  // Ensure active conversation exists
  useEffect(() => {
    if (!conversations[activeConvId]) {
      const ids = Object.keys(conversations);
      if (ids.length > 0) {
        setActiveConvId(ids[0]);
      }
    }
  }, [conversations, activeConvId]);

  // Persist conversations (user-scoped)
  useEffect(() => {
    saveConvs(userId, conversations);
  }, [userId, conversations]);

  // Persist active conv id (user-scoped)
  useEffect(() => {
    if (userId) localStorage.setItem(activeKey(userId), activeConvId);
  }, [userId, activeConvId]);

  const activeConv = conversations[activeConvId] || { messages: [] };

  const createConversation = useCallback(() => {
    const id = String(Date.now());
    setConversations((prev) => ({ ...prev, [id]: makeConv(id) }));
    setActiveConvId(id);
  }, []);

  const deleteConversation = useCallback((id) => {
    setConversations((prev) => {
      if (Object.keys(prev).length <= 1) return prev;
      const next = { ...prev };
      delete next[id];
      return next;
    });
    // If deleting the active conversation, switch to another
    setActiveConvId((prev) => {
      if (prev === id) {
        const remaining = Object.keys(conversations).filter((k) => k !== id);
        return remaining.length > 0 ? remaining[0] : prev;
      }
      return prev;
    });
  }, [conversations]);

  const updateConversationTitle = useCallback((id, title) => {
    setConversations((prev) => {
      if (!prev[id]) return prev;
      return { ...prev, [id]: { ...prev[id], title: title.trim() || prev[id].title } };
    });
  }, []);

  const setConvMessages = useCallback((idOrUpdater) => {
    setConversations((prev) => {
      const next = { ...prev };
      if (typeof idOrUpdater === 'function') {
        // Updater receives activeConvId and should return { id, messages }
        const result = idOrUpdater(activeConvId);
        if (result && next[result.id]) {
          next[result.id] = { ...next[result.id], messages: result.messages, title: result.title || next[result.id].title };
        }
      }
      return next;
    });
  }, [activeConvId]);

  // Convenience: messages of the active conversation
  const messages = activeConv.messages;
  const setMessages = useCallback((updater) => {
    setConversations((prev) => {
      const conv = prev[activeConvId];
      if (!conv) return prev;
      const newMessages = typeof updater === 'function' ? updater(conv.messages) : updater;
      return {
        ...prev,
        [activeConvId]: { ...conv, messages: newMessages },
      };
    });
  }, [activeConvId]);

  // Auto-title: use first user message
  useEffect(() => {
    const conv = conversations[activeConvId];
    if (!conv) return;
    if (conv.title !== '新对话') return;
    const firstUser = conv.messages.find((m) => m.role === 'user');
    if (firstUser) {
      const title = firstUser.content.slice(0, 24) + (firstUser.content.length > 24 ? '…' : '');
      setConversations((prev) => ({
        ...prev,
        [activeConvId]: { ...prev[activeConvId], title },
      }));
    }
  }, [messages, activeConvId, conversations]);

  // --- User ID ---
  const setUserId = useCallback((id) => {
    setUserIdState(id);
    if (id) {
      localStorage.setItem('mathguide_userId', id);
      // Load this user's conversations (or start fresh)
      const saved = loadConvs(id);
      setConversations(saved && Object.keys(saved).length > 0 ? saved : defaultConvs());
      const active = localStorage.getItem(activeKey(id));
      setActiveConvId(active && saved?.[active] ? active : '1');
    } else {
      localStorage.removeItem('mathguide_userId');
      setConversations(defaultConvs());
      setActiveConvId('1');
    }
  }, []);

  // --- Mastery ---
  const refreshMastery = useCallback(async () => {
    if (!userId) return;
    try {
      const data = await getMastery(userId);
      setMastery(data.mastery || {});
      setInitialized(true);
    } catch (err) {
      if (err.message?.includes('400') || err.message?.includes('未初始化')) {
        setInitialized(false);
      }
    }
  }, [userId]);

  const refreshNodes = useCallback(async () => {
    try {
      const [nodesData, chaptersData] = await Promise.all([getNodes(), getChapters()]);
      setNodes(nodesData);
      setChapters(chaptersData);
    } catch (err) {
      setError('加载知识点失败: ' + err.message);
    }
  }, []);

  useEffect(() => { refreshNodes(); }, [refreshNodes]);
  useEffect(() => { if (userId) refreshMastery(); }, [userId, refreshMastery]);

  const reset = useCallback(() => {
    setUserId('');
    setInitialized(false);
    setMastery({});
    setAdminToken(null);
  }, [setUserId]);

  const loginAdmin = useCallback(async (username, password) => {
    const data = await apiAdminLogin(username, password);
    setAdminToken(data.token);
  }, []);

  const logoutAdmin = useCallback(() => {
    setAdminToken(null);
  }, []);

  const ctxValue = useMemo(() => ({
    userId, setUserId,
    initialized, setInitialized,
    nodes, chapters,
    mastery, setMastery,
    messages, setMessages,
    loading, setLoading,
    error, setError,
    refreshMastery, refreshNodes,
    reset,
    // Conversations
    conversations, activeConvId, activeConv,
    createConversation, deleteConversation, updateConversationTitle,
    setActiveConvId,
    // Admin
    isAdmin, adminToken, loginAdmin, logoutAdmin,
  }), [
    userId, setUserId, initialized, nodes, chapters,
    mastery, messages, loading, error,
    refreshMastery, refreshNodes, reset,
    conversations, activeConvId, activeConv,
    createConversation, deleteConversation, updateConversationTitle, setMessages,
    isAdmin, adminToken, loginAdmin, logoutAdmin,
  ]);

  return (
    <UserContext.Provider value={ctxValue}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error('useUser must be used within UserProvider');
  return ctx;
}
