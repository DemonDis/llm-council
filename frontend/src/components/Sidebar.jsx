import { NavLink } from 'react-router-dom';
import '../styles/Sidebar.css';

const PAGES = [
  { path: '/roleplay', label: 'Ролевой штурм' },
  { path: '/ensemble', label: 'Битва моделей' },
];

// Список уже отфильтрован на бэкенде по IP и режиму страницы —
// все разговоры отсюда, с этого компьютера.
export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onOpenSettings,
}) {
  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>LLM Council</h1>
        <button className="new-conversation-btn" onClick={onNewConversation}>
          Новый разговор
        </button>
      </div>

      <nav className="page-tabs">
        {PAGES.map((page) => (
          <NavLink
            key={page.path}
            to={page.path}
            className={({ isActive }) =>
              `page-tab ${isActive ? 'active' : ''}`
            }
            title={
              page.path === '/roleplay'
                ? 'Вопрос цифровым личностям из roles.json'
                : 'Один вопрос — разным моделям совета'
            }
          >
            {page.label}
          </NavLink>
        ))}
      </nav>

      <div className="conversation-list">
        {conversations.length === 0 ? (
          <div className="no-conversations">Разговоров пока нет</div>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              className={`conversation-item ${
                conv.id === currentConversationId ? 'active' : ''
              }`}
              onClick={() => onSelectConversation(conv.id)}
            >
              <div className="conversation-row">
                <div className="conversation-title">
                  {conv.title || 'Новый разговор'}
                </div>
                <button
                  className="conversation-delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteConversation(conv.id);
                  }}
                  title="Удалить разговор"
                  aria-label="Удалить разговор"
                >
                  ×
                </button>
              </div>
              <div className="conversation-meta">
                {conv.message_count} сообщений · С этого компьютера
              </div>
            </div>
          ))
        )}
      </div>

      <div className="sidebar-footer">
        <button className="settings-btn" onClick={onOpenSettings}>
          Настройки API
        </button>
      </div>
    </div>
  );
}
