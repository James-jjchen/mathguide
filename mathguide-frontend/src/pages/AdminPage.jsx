import { useState, useEffect, useCallback } from 'react';
import { getAdminUsers, deleteAdminUser } from '../api/mathguide';
import { useUser } from '../context/UserContext';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';
import './AdminPage.css';

export default function AdminPage() {
  const { adminToken } = useUser();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deleteId, setDeleteId] = useState(null);
  const [confirmId, setConfirmId] = useState(null);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAdminUsers(adminToken);
      setUsers(data.users || []);
    } catch (e) {
      setError('加载用户列表失败: ' + e.message);
    } finally {
      setLoading(false);
    }
  }, [adminToken]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const handleDelete = async (userId) => {
    setDeleteId(userId);
    try {
      await deleteAdminUser(userId, adminToken);
      setUsers((prev) => prev.filter((u) => u.user_id !== userId));
      setConfirmId(null);
    } catch (e) {
      setError('删除失败: ' + e.message);
    } finally {
      setDeleteId(null);
    }
  };

  if (loading) return <div className="admin-loading"><LoadingSpinner message="加载用户数据..." /></div>;

  return (
    <div className="admin-page">
      <div className="admin-card">
        <div className="admin-header">
          <h1>管理面板</h1>
          <button className="admin-refresh" onClick={fetchUsers}>刷新</button>
        </div>

        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

        <div className="admin-stats">
          共 <strong>{users.length}</strong> 个用户
        </div>

        <table className="admin-table">
          <thead>
            <tr>
              <th>用户 ID</th>
              <th>已学节点</th>
              <th>平均掌握度</th>
              <th>练习次数</th>
              <th>最后活跃</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {users.length === 0 ? (
              <tr><td colSpan="6" className="admin-empty">暂无用户数据</td></tr>
            ) : (
              users.map((u) => (
                <tr key={u.user_id}>
                  <td className="admin-uid">{u.user_id}</td>
                  <td>{u.nodes_learned}/23</td>
                  <td>{Math.round(u.avg_mastery * 100)}%</td>
                  <td>{u.practice_count}</td>
                  <td className="admin-time">{u.last_active ? new Date(u.last_active).toLocaleString('zh-CN') : '-'}</td>
                  <td>
                    {confirmId === u.user_id ? (
                      <span className="admin-confirm">
                        <button className="admin-btn-danger" onClick={() => handleDelete(u.user_id)} disabled={deleteId === u.user_id}>
                          确认删除
                        </button>
                        <button className="admin-btn-cancel" onClick={() => setConfirmId(null)}>取消</button>
                      </span>
                    ) : (
                      <button className="admin-btn-del" onClick={() => setConfirmId(u.user_id)}>删除</button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
