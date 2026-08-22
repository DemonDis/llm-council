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
  theme,
  onToggleTheme,
}) {
  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-title-row">
          <h1>LLM Council</h1>
          <button
            className="theme-toggle"
            onClick={onToggleTheme}
            title={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
            aria-label={theme === 'dark' ? 'Включить светлую тему' : 'Включить тёмную тему'}
          >
            <svg className="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" />
              <line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" />
              <line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
            <svg className="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          </button>
        </div>
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
