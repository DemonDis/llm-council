import { useState, useEffect } from 'react';
import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  deviceId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onOpenSettings,
}) {
  const getDeviceLabel = (conv) => {
    if (conv.device_id === deviceId) return 'С этого компьютера';
    if (conv.device_name) return conv.device_name;
    return 'Другой компьютер';
  };

  const isOwn = (conv) => conv.device_id === deviceId || !conv.device_id;

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>LLM Council</h1>
        <button className="new-conversation-btn" onClick={onNewConversation}>
          + Новый разговор
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
                {isOwn(conv) && (
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
                {conv.message_count} сообщений · {getDeviceLabel(conv)}
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
