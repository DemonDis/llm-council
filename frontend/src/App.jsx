import { useState, useEffect } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import PlannerStub from './components/PlannerStub';
import Settings from './components/Settings';
import ConfirmDialog from './components/ConfirmDialog';
import { api } from './api';
import './styles/App.css';

const SETTINGS_STORAGE_KEY = 'llm_council_settings';
const DEVICE_ID_STORAGE_KEY = 'llm_council_device_id';

function loadSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_STORAGE_KEY);
    return raw ? JSON.parse(raw) : { apiKey: '' };
  } catch (e) {
    return { apiKey: '' };
  }
}

function loadDeviceId() {
  let id = localStorage.getItem(DEVICE_ID_STORAGE_KEY);
  if (!id) {
    // Используем fallback для сред без поддержки crypto.randomUUID (например, http без localhost)
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      id = crypto.randomUUID();
    } else {
      // Fallback генератор UUID v4
      id = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
      });
    }
    localStorage.setItem(DEVICE_ID_STORAGE_KEY, id);
  }
  return id;
}

// Иммутабельно обновляет последнее сообщение разговора.
// Важно: updater-функции в StrictMode вызываются React дважды, поэтому
// мутировать объекты из prev нельзя — иначе чанки стрима добавляются по два раза.
function updateLastMessage(prev, transform) {
  if (!prev?.messages?.length) return prev;
  const messages = [...prev.messages];
  const last = messages[messages.length - 1];
  const clone = {
    ...last,
    loading: { ...last.loading },
    streamingSlots: { ...last.streamingSlots },
    streamingSlotsStage2: { ...last.streamingSlotsStage2 },
    streamingStage3: last.streamingStage3 ? { ...last.streamingStage3 } : null,
  };
  messages[messages.length - 1] = transform(clone);
  return { ...prev, messages };
}

function CouncilPage({ mode, deviceId, settings, onOpenSettings }) {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Load conversations on mount
  useEffect(() => {
    loadConversations();
  }, []);

  // Load conversation details when selected
  useEffect(() => {
    if (currentConversationId) {
      loadConversation(currentConversationId);
    }
  }, [currentConversationId]);

  const loadConversations = async () => {
    try {
      const convs = await api.listConversations(mode);
      setConversations(convs);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  const loadConversation = async (id) => {
    try {
      const conv = await api.getConversation(id);
      setCurrentConversation(conv);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  const handleNewConversation = async () => {
    try {
      const newConv = await api.createConversation({
        device_id: deviceId,
        mode,
      });
      setConversations([
        {
          id: newConv.id,
          created_at: newConv.created_at,
          mode: newConv.mode,
          message_count: 0,
          device_id: deviceId,
        },
        ...conversations,
      ]);
      setCurrentConversationId(newConv.id);
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleSelectConversation = (id) => {
    setCurrentConversationId(id);
  };

  const handleDeleteConversation = async (id) => {
    setIsDeleting(true);
    try {
      await api.deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (currentConversationId === id) {
        setCurrentConversationId(null);
        setCurrentConversation(null);
      }
      setDeleteTarget(null);
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    } finally {
      setIsDeleting(false);
    }
  };

  // Локальные значения из настроек имеют приоритет над .env.
  // Если локальное значение пустое — параметр не отправляется, бэкенд использует .env.
  const credentials = {
    ...(settings.apiKey ? { api_key: settings.apiKey } : {}),
    device_id: deviceId,
  };

  const handleSendMessage = async (content) => {
    if (!currentConversationId) return;

    setIsLoading(true);
    try {
      // Optimistically add user message to UI
      const userMessage = { role: 'user', content };
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
      }));

      // Create a partial assistant message that will be updated progressively
      const assistantMessage = {
        role: 'assistant',
        stage1: null,
        stage2: null,
        stage3: null,
        metadata: null,
        streamingSlots: {},
        streamingSlotsStage2: {},
        streamingStage3: null,
        rolesTotal: 0,
        activeRoleIndex: -1,
        activeRoleIndexStage2: -1,
        loading: {
          stage1: false,
          stage2: false,
          stage3: false,
        },
      };

      // Add the partial assistant message
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, assistantMessage],
      }));

      // Send message with streaming
      await api.sendMessageStream(
        currentConversationId,
        content,
        mode,
        credentials,
        (eventType, event) => {
          switch (eventType) {
            case 'stage1_start':
              setCurrentConversation((prev) =>
                updateLastMessage(prev, (m) => ({
                  ...m,
                  loading: { ...m.loading, stage1: true },
                  rolesTotal: event.roles_total || m.rolesTotal,
                }))
              );
              break;

            case 'stage1_complete':
              setCurrentConversation((prev) =>
                updateLastMessage(prev, (m) => ({
                  ...m,
                  stage1: event.data,
                  loading: { ...m.loading, stage1: false },
                  streamingSlots: {},
                  activeRoleIndex: -1,
                }))
              );
              break;

            case 'stage1_role_start':
              setCurrentConversation((prev) =>
                updateLastMessage(prev, (m) => ({
                  ...m,
                  streamingSlots: {
                    ...m.streamingSlots,
                    [event.index]: { role: event.role, response: '' },
                  },
                }))
              );
              break;

            case 'stage1_role_active':
              setCurrentConversation((prev) =>
                updateLastMessage(prev, (m) => ({
                  ...m,
                  activeRoleIndex: event.index,
                }))
              );
              break;

            case 'stage1_chunk':
              setCurrentConversation((prev) =>
                updateLastMessage(prev, (m) => {
                  const slot = m.streamingSlots[event.index];
                  if (!slot) return m;
                  return {
                    ...m,
                    streamingSlots: {
                      ...m.streamingSlots,
                      [event.index]: { ...slot, response: slot.response + event.content },
                    },
                  };
                })
              );
              break;

            case 'stage3_role_start':
              setCurrentConversation((prev) =>
                updateLastMessage(prev, (m) => ({
                  ...m,
                  streamingStage3: { model: event.model, response: '' },
                }))
              );
              break;

            case 'stage3_chunk':
              setCurrentConversation((prev) =>
                updateLastMessage(prev, (m) => {
                  if (!m.streamingStage3) return m;
                  return {
                    ...m,
                    streamingStage3: {
                      ...m.streamingStage3,
                      response: m.streamingStage3.response + event.content,
                    },
                  };
                })
              );
              break;

            case 'stage2_start':
              setCurrentConversation((prev) =>
                updateLastMessage(prev, (m) => ({
                  ...m,
                  loading: { ...m.loading, stage2: true },
                }))
              );
              break;

            case 'stage2_role_start':
              setCurrentConversation((prev) =>
                updateLastMessage(prev, (m) => ({
                  ...m,
                  streamingSlotsStage2: {
                    ...m.streamingSlotsStage2,
                    [event.index]: { role: event.role, ranking: '' },
                  },
                }))
              );
              break;

            case 'stage2_role_active':
              setCurrentConversation((prev) =>
                updateLastMessage(prev, (m) => ({
                  ...m,
                  activeRoleIndexStage2: event.index,
                }))
              );
              break;

            case 'stage2_chunk':
              setCurrentConversation((prev) =>
                updateLastMessage(prev, (m) => {
                  const slot = m.streamingSlotsStage2[event.index];
                  if (!slot) return m;
                  return {
                    ...m,
                    streamingSlotsStage2: {
                      ...m.streamingSlotsStage2,
                      [event.index]: { ...slot, ranking: slot.ranking + event.content },
                    },
                  };
                })
              );
              break;

            case 'stage2_complete':
              setCurrentConversation((prev) =>
                updateLastMessage(prev, (m) => ({
                  ...m,
                  stage2: event.data,
                  metadata: event.metadata,
                  loading: { ...m.loading, stage2: false },
                  streamingSlotsStage2: {},
                  activeRoleIndexStage2: -1,
                }))
              );
              break;

            case 'stage3_start':
              setCurrentConversation((prev) =>
                updateLastMessage(prev, (m) => ({
                  ...m,
                  loading: { ...m.loading, stage3: true },
                }))
              );
              break;

            case 'stage3_complete':
              setCurrentConversation((prev) =>
                updateLastMessage(prev, (m) => ({
                  ...m,
                  stage3: event.data,
                  loading: { ...m.loading, stage3: false },
                  streamingStage3: null,
                }))
              );
              break;

            case 'title_complete':
              // Reload conversations to get updated title
              loadConversations();
              break;

            case 'complete':
              // Stream complete, reload conversations list
              loadConversations();
              setIsLoading(false);
              break;

            case 'error':
              console.error('Stream error:', event.message);
              setCurrentConversation((prev) =>
                updateLastMessage(prev, (m) => ({
                  ...m,
                  loading: { stage1: false, stage2: false, stage3: false },
                }))
              );
              setIsLoading(false);
              break;

            default:
              console.log('Unknown event type:', eventType);
          }
        }
      );
    } catch (error) {
      console.error('Failed to send message:', error);
      // Remove optimistic messages on error
      setCurrentConversation((prev) => ({
        ...prev,
        messages: prev.messages.slice(0, -2),
      }));
      setIsLoading(false);
    }
  };

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onDeleteConversation={setDeleteTarget}
        onOpenSettings={onOpenSettings}
      />
      <ChatInterface
        conversation={currentConversation}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        mode={mode}
      />
      {deleteTarget && (
        <ConfirmDialog
          title="Удалить этот разговор?"
          message={`«${
            conversations.find((c) => c.id === deleteTarget)?.title ||
            'Новый разговор'
          }» будет удалён безвозвратно.`}
          busy={isDeleting}
          onConfirm={() => handleDeleteConversation(deleteTarget)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}

// Страница-заглушка «Планировщик»: тот же каркас с сайдбаром,
// но без разговоров, пока режим не реализован на бэкенде.
function PlannerPage({ onOpenSettings }) {
  return (
    <div className="app">
      <Sidebar
        conversations={[]}
        currentConversationId={null}
        onSelectConversation={() => {}}
        onNewConversation={null}
        onDeleteConversation={() => {}}
        onOpenSettings={onOpenSettings}
      />
      <PlannerStub />
    </div>
  );
}

export default function App() {
  const [settings, setSettings] = useState(loadSettings);
  const [envConfig, setEnvConfig] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [deviceId] = useState(loadDeviceId);

  // Backend config нужен только модалке настроек — грузим один раз на всё приложение
  useEffect(() => {
    api
      .getConfig()
      .then(setEnvConfig)
      .catch((error) => console.error('Failed to load config:', error));
  }, []);

  const handleSaveSettings = (newSettings) => {
    setSettings(newSettings);
    localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(newSettings));
  };

  const handleClearSettings = () => {
    setSettings({ apiKey: '' });
    localStorage.removeItem(SETTINGS_STORAGE_KEY);
  };

  const openSettings = () => setShowSettings(true);

  return (
    <>
      <Routes>
        <Route
          path="/ensemble"
          element={
            <CouncilPage
              key="ensemble"
              mode="ensemble"
              deviceId={deviceId}
              settings={settings}
              onOpenSettings={openSettings}
            />
          }
        />
        <Route
          path="/roleplay"
          element={
            <CouncilPage
              key="roleplay"
              mode="roleplay"
              deviceId={deviceId}
              settings={settings}
              onOpenSettings={openSettings}
            />
          }
        />
        {/* Заглушка: режим пока не реализован на бэкенде */}
        <Route path="/planner" element={<PlannerPage onOpenSettings={openSettings} />} />
        {/* Ролевой режим — основной сценарий, открывается по умолчанию */}
        <Route path="*" element={<Navigate to="/roleplay" replace />} />
      </Routes>
      {showSettings && (
        <Settings
          envConfig={envConfig}
          settings={settings}
          onSave={handleSaveSettings}
          onClear={handleClearSettings}
          onClose={() => setShowSettings(false)}
        />
      )}
    </>
  );
}
