import { useState, useEffect } from 'react';
import { getDimMastery, getRecommendV2 } from '../api/mathguide';
import './DevMode.css';

export default function DevMode({ userId, onClose }) {
  const [dimData, setDimData] = useState(null);
  const [recData, setRecData] = useState(null);
  const [apiUrl, setApiUrl] = useState('/api/dim-mastery?user_id=' + userId);
  const [apiResult, setApiResult] = useState('');
  const [tab, setTab] = useState('dims');

  useEffect(() => {
    getDimMastery(userId).then(setDimData).catch(console.error);
    getRecommendV2(userId).then(setRecData).catch(console.error);
  }, [userId]);

  async function callApi() {
    try {
      const res = await fetch(apiUrl);
      const data = await res.json();
      setApiResult(JSON.stringify(data, null, 2));
    } catch (e) {
      setApiResult('Error: ' + e.message);
    }
  }

  return (
    <div className="dev-overlay">
      <div className="dev-panel">
        <div className="dev-header">
          <h3>Dev Mode</h3>
          <button onClick={onClose}>×</button>
        </div>

        <div className="dev-tabs">
          <button className={tab === 'dims' ? 'active' : ''} onClick={() => setTab('dims')}>维度数据</button>
          <button className={tab === 'rec' ? 'active' : ''} onClick={() => setTab('rec')}>推荐数据</button>
          <button className={tab === 'api' ? 'active' : ''} onClick={() => setTab('api')}>API 调试</button>
        </div>

        <div className="dev-content">
          {tab === 'dims' && dimData && (
            <table className="dev-table">
              <thead>
                <tr>
                  <th>dim_id</th>
                  <th>name</th>
                  <th>α</th>
                  <th>β</th>
                  <th>mastery</th>
                  <th>confidence</th>
                  <th>stuck</th>
                </tr>
              </thead>
              <tbody>
                {dimData.dimensions?.map(d => (
                  <tr key={d.dim_id}>
                    <td>{d.dim_id}</td>
                    <td>{d.name}</td>
                    <td>{d.alpha}</td>
                    <td>{d.beta}</td>
                    <td>{d.mastery.toFixed(3)}</td>
                    <td>{d.confidence.toFixed(1)}</td>
                    <td>{d.stuck_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {tab === 'rec' && recData && (
            <div className="dev-json">
              <pre>{JSON.stringify(recData, null, 2)}</pre>
            </div>
          )}

          {tab === 'api' && (
            <div className="dev-api">
              <div className="dev-api-input">
                <input
                  type="text"
                  value={apiUrl}
                  onChange={e => setApiUrl(e.target.value)}
                  placeholder="/api/..."
                />
                <button onClick={callApi}>调用</button>
              </div>
              <pre className="dev-api-result">{apiResult || '点击调用查看结果'}</pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
