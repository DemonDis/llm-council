import './Sidebar.css';

function getDeviceLabel(conv, deviceId) {
  if (conv.device_id === deviceId) return 'С этого компьютера';
  if (conv.device_ip) return conv.device_ip;
  return 'Другой компьютер';
}

function isOwn(conv, deviceId) {
  return conv.device_id === deviceId || !conv.device_id;
}

export default function Sidebar({
  conversations,
  currentConversationId,
  deviceId,
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
                {isOwn(conv, deviceId) && (
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
                )}
              </div>
              <div className="conversation-meta">
                {conv.message_count} сообщений · {getDeviceLabel(conv, deviceId)}
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
