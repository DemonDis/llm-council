import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import './ChatInterface.css';

const MODES = [
  { value: 'ensemble', label: 'Битва моделей', description: 'Один вопрос — разным моделям' },
  { value: 'roleplay', label: 'Ролевой мозговой штурм', description: null },
];

function roleplayDescription(roles) {
  if (!roles || roles.length === 0) return 'Роли: см. roles.json';
  return `Роли: ${roles.join(', ')}`;
}

const LOADING_TEXTS = {
  stage1: {
    ensemble: 'Этап 1: собираем ответы моделей...',
    roleplay: 'Этап 1: собираем мнения ролей...',
  },
  stage2: {
    ensemble: 'Этап 2: взаимное ранжирование моделей...',
    roleplay: 'Этап 2: взаимное ранжирование ролей...',
  },
  stage3: 'Этап 3: синтез итогового ответа...',
};

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
  mode,
  onModeChange,
  roles,
}) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  if (!conversation) {
    return (
      <div className="chat-interface">
        <div className="empty-state">
          <h2>Добро пожаловать в LLM Council</h2>
          <p>Создайте новый разговор, чтобы начать</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-interface">
      <div className="messages-container">
        {conversation.messages.length === 0 ? (
          <div className="empty-state">
            <h2>Начните разговор</h2>
            <p>Задайте вопрос, чтобы посоветоваться с LLM Council</p>
          </div>
        ) : (
          conversation.messages.map((msg, index) => (
            <div key={index} className="message-group">
              {msg.role === 'user' ? (
                <div className="user-message">
                  <div className="message-label">Вы</div>
                  <div className="message-content">
                    <div className="markdown-content">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="assistant-message">
                  <div className="message-label">LLM Council</div>

                  {/* Stage 1 */}
                  {msg.loading?.stage1 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>{LOADING_TEXTS.stage1[mode]}</span>
                    </div>
                  )}
                  {msg.stage1 && <Stage1 responses={msg.stage1} />}

                  {/* Stage 2 */}
                  {msg.loading?.stage2 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>{LOADING_TEXTS.stage2[mode]}</span>
                    </div>
                  )}
                  {msg.stage2 && (
                    <Stage2
                      rankings={msg.stage2}
                      labelToModel={msg.metadata?.label_to_model}
                      aggregateRankings={msg.metadata?.aggregate_rankings}
                      mode={mode}
                    />
                  )}

                  {/* Stage 3 */}
                  {msg.loading?.stage3 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>{LOADING_TEXTS.stage3}</span>
                    </div>
                  )}
                  {msg.stage3 && <Stage3 finalResponse={msg.stage3} />}
                </div>
              )}
            </div>
          ))
        )}

        {isLoading && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            <span>Совет размышляет...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="mode-selector">
        {MODES.map((m) => (
          <button
            key={m.value}
            className={`mode-button ${mode === m.value ? 'active' : ''}`}
            onClick={() => onModeChange(m.value)}
            disabled={isLoading}
            title={m.value === 'roleplay' ? roleplayDescription(roles) : m.description}
          >
            {m.label}
          </button>
        ))}
      </div>

      <form className="input-form" onSubmit={handleSubmit}>
        <textarea
          className="message-input"
          placeholder="Задайте вопрос... (Shift+Enter — новая строка, Enter — отправить)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          rows={3}
        />
        <button
          type="submit"
          className="send-button"
          disabled={!input.trim() || isLoading}
        >
          Отправить
        </button>
      </form>
    </div>
  );
}
