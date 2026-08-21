import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { Stage1, Stage2, Stage3 } from './index';
import '../styles/ChatInterface.css';

const LOADING_TEXTS = {
  stage1: {
    ensemble: 'Этап 1: собираем ответы моделей...',
    roleplay: 'Этап 1: начинаем опрос ролей...',
  },
  stage2: {
    ensemble: 'Этап 2: взаимное ранжирование моделей...',
    roleplay: 'Этап 2: взаимное ранжирование ролей...',
  },
  stage3: 'Этап 3: синтез итогового ответа...',
};

function getRoleProgress(msg, mode) {
  if (mode !== 'roleplay') return null;
  const slots = msg.streamingSlots || {};
  const indices = Object.keys(slots).map(Number);
  if (indices.length === 0) return null;
  const total = msg.rolesTotal || indices.length;
  const activeIdx = msg.activeRoleIndex ?? -1;
  const activeRole = activeIdx >= 0 ? slots[activeIdx] : null;
  const doneCount = indices.filter(i => {
    const s = slots[i];
    return s && s.response.length > 0 && i < activeIdx;
  }).length;
  return {
    current: Math.max(activeIdx + 1, 1),
    total,
    role: activeRole?.role || slots[indices[indices.length - 1]]?.role || '',
    hasContent: (activeRole?.response || '').length > 0,
    doneCount,
  };
}

function getRoleProgressStage2(msg, mode) {
  if (mode !== 'roleplay') return null;
  const slots = msg.streamingSlotsStage2 || {};
  const indices = Object.keys(slots).map(Number);
  if (indices.length === 0) return null;
  const total = msg.rolesTotal || indices.length;
  const activeIdx = msg.activeRoleIndexStage2 ?? -1;
  const activeRole = activeIdx >= 0 ? slots[activeIdx] : null;
  const doneCount = indices.filter(i => {
    const s = slots[i];
    return s && s.ranking.length > 0 && i < activeIdx;
  }).length;
  return {
    current: Math.max(activeIdx + 1, 1),
    total,
    role: activeRole?.role || slots[indices[indices.length - 1]]?.role || '',
    hasContent: (activeRole?.ranking || '').length > 0,
    doneCount,
  };
}

function RoleProgressIndicator({ progress, prefix }) {
  if (!progress) return null;
  return (
    <div className="role-progress">
      <div className="role-progress-bar">
        <div
          className="role-progress-fill"
          style={{ width: `${(progress.doneCount / progress.total) * 100}%` }}
        />
      </div>
      <div className="role-progress-text">
        {prefix} {progress.current} из {progress.total}: {progress.role}
        {!progress.hasContent && <span className="progress-waiting"> — ожидание ответа...</span>}
      </div>
    </div>
  );
}

function StageLoading({ text }) {
  return (
    <div className="stage-loading">
      <div className="spinner" />
      <span>{text}</span>
    </div>
  );
}

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
  mode,
}) {
  const [input, setInput] = useState('');
  const [inputHeight, setInputHeight] = useState(72);
  const messagesEndRef = useRef(null);

  const INPUT_MIN_HEIGHT = 48;
  const INPUT_MAX_HEIGHT = 240;
  const INPUT_DEFAULT_HEIGHT = 72;

  // Тянем верхний край поля: движение мыши вверх увеличивает высоту
  const handleResizeStart = (e) => {
    e.preventDefault();
    const startY = e.clientY;
    const startHeight = inputHeight;
    const onMove = (ev) => {
      const next = startHeight + (startY - ev.clientY);
      setInputHeight(
        Math.min(INPUT_MAX_HEIGHT, Math.max(INPUT_MIN_HEIGHT, next))
      );
    };
    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation?.messages?.length]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  if (!conversation) {
    return (
      <div className="chat-interface">
        <div className="empty-state">
          <div className="empty-state-icon">💬</div>
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
            <div className="empty-state-icon">💬</div>
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

                  {msg.loading?.stage1 && !msg.stage1 && Object.keys(msg.streamingSlots || {}).length === 0 && (
                    <StageLoading text={LOADING_TEXTS.stage1[mode]} />
                  )}
                  <RoleProgressIndicator
                    progress={getRoleProgress(msg, mode)}
                    prefix="Запрос"
                  />
                  {msg.stage1 ? (
                    <Stage1 responses={msg.stage1} />
                  ) : (
                    <Stage1 streamingSlots={msg.streamingSlots} />
                  )}

                  {msg.loading?.stage2 && !msg.stage2 && Object.keys(msg.streamingSlotsStage2 || {}).length === 0 && (
                    <StageLoading text={LOADING_TEXTS.stage2[mode]} />
                  )}
                  <RoleProgressIndicator
                    progress={getRoleProgressStage2(msg, mode)}
                    prefix="Оценка"
                  />
                  {msg.stage2 ? (
                    <Stage2
                      rankings={msg.stage2}
                      labelToModel={msg.metadata?.label_to_model}
                      aggregateRankings={msg.metadata?.aggregate_rankings}
                      mode={mode}
                    />
                  ) : (
                    <Stage2
                      streamingSlots={msg.streamingSlotsStage2}
                      rolesTotal={msg.rolesTotal}
                      mode={mode}
                    />
                  )}

                  {msg.loading?.stage3 && !msg.stage3 && !msg.streamingStage3 && (
                    <StageLoading text={LOADING_TEXTS.stage3} />
                  )}
                  {(msg.stage3 || msg.streamingStage3) && (
                    <Stage3
                      finalResponse={msg.stage3}
                      streamingResponse={!msg.stage3 ? msg.streamingStage3 : null}
                    />
                  )}
                </div>
              )}
            </div>
          ))
        )}

        {isLoading && (
          <div className="loading-indicator">
            <div className="spinner" />
            <span>Совет размышляет...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form className="input-form" onSubmit={handleSubmit}>
        <div className="input-wrapper">
          <div
            className="input-resize-handle"
            onPointerDown={handleResizeStart}
            onDoubleClick={() => setInputHeight(INPUT_DEFAULT_HEIGHT)}
            title="Потяните вверх, чтобы расширить (двойной клик — сброс)"
          />
          <textarea
            className="message-input"
            style={{ height: inputHeight }}
            placeholder="Задайте вопрос... (Shift+Enter — новая строка)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            rows={2}
          />
        </div>
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
