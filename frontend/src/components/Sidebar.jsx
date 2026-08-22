import { NavLink } from 'react-router-dom';
import '../styles/Sidebar.css';

const PAGES = [
  {
    path: '/roleplay',
    label: 'Ролевой штурм',
    icon: '🎭',
    title: 'Вопрос цифровым личностям из roles.json',
  },
  {
    path: '/staff',
    label: 'Командный штаб',
    icon: '🎖️',
    title: 'Команда офицеров разрабатывает план по вашей задаче (в разработке)',
  },
  {
    path: '/dialogue',
    label: 'Диалог с руководителем',
    icon: '👔',
    title: 'Личный разговор с цифровым руководителем (в разработке)',
  },
  {
    path: '/ensemble',
    label: 'Битва моделей',
    icon: '⚔️',
    title: 'Один вопрос — разным моделям совета',
  },
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
        <button
          className="new-conversation-btn"
          onClick={onNewConversation}
          disabled={!onNewConversation}
          title={onNewConversation ? undefined : 'Режим ещё в разработке'}
        >
          Новый разговор
        </button>
      </div>

      <nav className="page-nav">
        {PAGES.map((page) => (
          <NavLink
            key={page.path}
            to={page.path}
            className={({ isActive }) =>
              `page-nav-item ${isActive ? 'active' : ''}`
            }
            title={page.title}
          >
            <span className="page-nav-icon" aria-hidden="true">
              {page.icon}
            </span>
            <span className="page-nav-label">{page.label}</span>
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
