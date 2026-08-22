import { useEffect, useState } from 'react';
import { api } from '../utils';
import '../styles/ChatInterface.css';

// Экран выбора участников штаба перед началом совещания.
// Мультивыбор: можно выбрать несколько человек или всех сразу.
// onStart(members) получает массив выбранных профилей [{ id, name, ... }].
export default function StaffPicker({ onStart }) {
  const [members, setMembers] = useState(null);
  const [failed, setFailed] = useState(false);
  const [selectedIds, setSelectedIds] = useState(new Set());

  useEffect(() => {
    let cancelled = false;
    api
      .getStaff('personnel')
      .then((list) => {
        if (!cancelled) setMembers(list);
      })
      .catch((error) => {
        console.error('Failed to load staff:', error);
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const available = (members || []).filter((m) => m.status === 'active');
  const allSelected = available.length > 0 && available.every((m) => selectedIds.has(m.id));

  const toggle = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    setSelectedIds(
      allSelected ? new Set() : new Set(available.map((m) => m.id))
    );
  };

  const start = () => {
    const chosen = (members || []).filter((m) => selectedIds.has(m.id));
    if (chosen.length > 0) onStart(chosen);
  };

  return (
    <div className="chat-interface">
      <div className="empty-state">
        <div className="empty-state-icon">🎖️</div>
        <h2>Командный штаб</h2>
        <p>Выберите офицеров для совещания — можно несколько или всех сразу</p>

        {failed ? (
          <p>Не удалось загрузить список сотрудников</p>
        ) : !members ? (
          <p>Загружаем список…</p>
        ) : (
          <>
            <div className="staff-actions">
              <button type="button" className="staff-toggle-all" onClick={toggleAll}>
                {allSelected ? 'Снять выделение' : 'Выбрать всех'}
              </button>
              {selectedIds.size > 0 && (
                <span className="staff-count">Выбрано: {selectedIds.size}</span>
              )}
            </div>
            <ul className="leader-list">
              {members.map((member) => (
                <li key={member.id}>
                  <button
                    type="button"
                    className={`leader-chip${
                      member.status !== 'active' ? ' inactive' : ''
                    }${selectedIds.has(member.id) ? ' selected' : ''}`}
                    onClick={() => toggle(member.id)}
                    disabled={member.status !== 'active'}
                    title={
                      member.status !== 'active'
                        ? 'Профиль неактивен'
                        : undefined
                    }
                  >
                    {member.name}
                  </button>
                </li>
              ))}
            </ul>
            <button
              type="button"
              className="send-button staff-start"
              onClick={start}
              disabled={selectedIds.size === 0}
            >
              Созвать штаб ({selectedIds.size})
            </button>
          </>
        )}
      </div>
    </div>
  );
}
