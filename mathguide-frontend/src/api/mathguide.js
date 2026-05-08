const BASE = '/api';
const TIMEOUT = 60000;

async function request(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT);

  try {
    const res = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || `HTTP ${res.status}`);
    }
    return data;
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new Error('请求超时，请检查网络连接');
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export async function getNodes() {
  return request(`${BASE}/nodes`);
}

export async function getNode(nodeId) {
  return request(`${BASE}/node/${nodeId}`);
}

export async function getChapters() {
  return request(`${BASE}/chapters`);
}

export async function initUser(userId, { chapterIds = [], nodeMastery = null } = {}) {
  const body = { user_id: userId };
  if (nodeMastery && Object.keys(nodeMastery).length > 0) {
    body.node_mastery = nodeMastery;
  } else if (chapterIds.length > 0) {
    body.chapter_ids = chapterIds;
  }
  return request(`${BASE}/init_user`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function askQuestion(question, userId, learnedIds = null) {
  const body = { question, user_id: userId };
  if (learnedIds !== null) {
    body.learned_ids = learnedIds;
  }
  return request(`${BASE}/ask`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function askQuestionStream(question, userId, learnedIds = null, { onThinking, onToken, onDone, onError }) {
  const body = { question, user_id: userId };
  if (learnedIds !== null) {
    body.learned_ids = learnedIds;
  }

  const controller = new AbortController();

  fetch(`${BASE}/ask/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: controller.signal,
  }).then(async (response) => {
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      onError(new Error(err.error || `HTTP ${response.status}`));
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6);
        if (data === '[DONE]') { onDone(); return; }
        try {
          const parsed = JSON.parse(data);
          if (parsed.error) { onError(new Error(parsed.error)); return; }
          const delta = parsed.choices?.[0]?.delta || {};
          // Separate reasoning (internal) from content (displayed)
          if (delta.reasoning_content && onThinking) onThinking(delta.reasoning_content);
          if (delta.content && onToken) onToken(delta.content);
        } catch { /* skip unparseable chunks */ }
      }
    }
    onDone();
  }).catch((err) => {
    if (err.name !== 'AbortError') onError(err);
  });

  return () => controller.abort();
}

export async function getRecommendation(userId, strategy = 'auto') {
  return request(`${BASE}/recommend`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, strategy }),
  });
}

export async function getMastery(userId) {
  return request(`${BASE}/mastery?user_id=${encodeURIComponent(userId)}`);
}

export async function diagnoseKnowledge(userId, nodeId, studentAnswer) {
  return request(`${BASE}/diagnose`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, node_id: nodeId, student_answer: studentAnswer }),
  });
}

export async function diagnoseWeaknesses(userId) {
  return request(`${BASE}/diagnose-weaknesses`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId }),
  });
}

export async function generatePractice(userId, nodeIds = null, count = 3) {
  const body = { user_id: userId, count };
  if (nodeIds) {
    body.node_ids = nodeIds;
  }
  return request(`${BASE}/generate-practice`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function submitPractice(userId, answers) {
  return request(`${BASE}/submit-practice`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, answers }),
  });
}

export async function getStageMap(userId) {
  return request(`${BASE}/stage-map?user_id=${encodeURIComponent(userId)}`);
}

export async function getPracticeHistory(userId, limit = 20) {
  return request(`${BASE}/practice-history?user_id=${encodeURIComponent(userId)}&limit=${limit}`);
}

export async function resetMastery(userId) {
  return request(`${BASE}/reset_mastery`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId }),
  });
}

export async function resetAll() {
  return request(`${BASE}/reset`, {
    method: 'POST',
  });
}

export async function adminLogin(username, password) {
  return request(`${BASE}/admin/login`, {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}

export async function getAdminUsers(token) {
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  return request(`${BASE}/admin/users`, { headers });
}

export async function deleteAdminUser(userId, token) {
  return request(`${BASE}/admin/users/${encodeURIComponent(userId)}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  });
}
