import { useEffect, useState } from 'react';
import { api } from '../utils';
import '../styles/ChatInterface.css';

// Экран выбора руководителя перед началом диалога.
// Клик по чипу сразу начинает диалог: onStart(leader) → { id, name, ... }.
export default function LeaderPicker({ onStart }) {
  const [leaders, setLeaders] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getStaff('leaders')
      .then((list) => {
        if (!cancelled) setLeaders(list);
      })
      .catch((error) => {
        console.error('Failed to load leaders:', error);
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="chat-interface">
      <div className="empty-state">
        <div className="empty-state-icon">👔</div>
        <h2>Диалог с руководителем</h2>
        <p>Выберите руководителя для личного разговора</p>

        {failed ? (
          <p>Не удалось загрузить список руководителей</p>
        ) : !leaders ? (
          <p>Загружаем список…</p>
        ) : (
          <ul className="leader-list">
            {leaders.map((leader) => (
              <li key={leader.id}>
                <button
                  type="button"
                  className={`leader-chip${
                    leader.status !== 'active' ? ' inactive' : ''
                  }`}
                  onClick={() => onStart(leader)}
                  disabled={leader.status !== 'active'}
                  title={
                    leader.status !== 'active'
                      ? 'Профиль неактивен'
                      : undefined
                  }
                >
                  {leader.name}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
