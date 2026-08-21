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

function CouncilPage({ mode }) {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [settings, setSettings] = useState(loadSettings);
  const [envConfig, setEnvConfig] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [deviceId] = useState(loadDeviceId);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Load conversations and backend config on mount
  useEffect(() => {
    loadConversations();
    api
      .getConfig()
      .then(setEnvConfig)
      .catch((error) => console.error('Failed to load config:', error));
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

  const handleSaveSettings = (newSettings) => {
    setSettings(newSettings);
    localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(newSettings));
  };

  const handleClearSettings = () => {
    setSettings({ apiKey: '' });
    localStorage.removeItem(SETTINGS_STORAGE_KEY);
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
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                lastMsg.loading.stage1 = true;
                if (event.roles_total) {
                  lastMsg.rolesTotal = event.roles_total;
                }
                return { ...prev, messages };
              });
              break;

            case 'stage1_complete':
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                lastMsg.stage1 = event.data;
                lastMsg.loading.stage1 = false;
                lastMsg.streamingSlots = {};
                lastMsg.activeRoleIndex = -1;
                return { ...prev, messages };
              });
              break;

            case 'stage1_role_start':
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                lastMsg.streamingSlots = {
                  ...lastMsg.streamingSlots,
                  [event.index]: { role: event.role, response: '' },
                };
                return { ...prev, messages };
              });
              break;

            case 'stage1_role_active':
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                lastMsg.activeRoleIndex = event.index;
                return { ...prev, messages };
              });
              break;

            case 'stage1_chunk':
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                const slots = { ...lastMsg.streamingSlots };
                if (slots[event.index]) {
                  slots[event.index] = {
                    ...slots[event.index],
                    response: slots[event.index].response + event.content,
                  };
                }
                lastMsg.streamingSlots = slots;
                return { ...prev, messages };
              });
              break;

            case 'stage3_role_start':
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                lastMsg.streamingStage3 = { model: event.model, response: '' };
                return { ...prev, messages };
              });
              break;

            case 'stage3_chunk':
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                if (lastMsg.streamingStage3) {
                  lastMsg.streamingStage3 = {
                    ...lastMsg.streamingStage3,
                    response: lastMsg.streamingStage3.response + event.content,
                  };
                }
                return { ...prev, messages };
              });
              break;

            case 'stage2_start':
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                lastMsg.loading.stage2 = true;
                return { ...prev, messages };
              });
              break;

            case 'stage2_role_start':
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                lastMsg.streamingSlotsStage2 = {
                  ...lastMsg.streamingSlotsStage2,
                  [event.index]: { role: event.role, ranking: '' },
                };
                return { ...prev, messages };
              });
              break;

            case 'stage2_role_active':
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                lastMsg.activeRoleIndexStage2 = event.index;
                return { ...prev, messages };
              });
              break;

            case 'stage2_chunk':
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                const slots = { ...lastMsg.streamingSlotsStage2 };
                if (slots[event.index]) {
                  slots[event.index] = {
                    ...slots[event.index],
                    ranking: slots[event.index].ranking + event.content,
                  };
                }
                lastMsg.streamingSlotsStage2 = slots;
                return { ...prev, messages };
              });
              break;

            case 'stage2_complete':
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                lastMsg.stage2 = event.data;
                lastMsg.metadata = event.metadata;
                lastMsg.loading.stage2 = false;
                lastMsg.streamingSlotsStage2 = {};
                lastMsg.activeRoleIndexStage2 = -1;
                return { ...prev, messages };
              });
              break;

            case 'stage3_start':
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                lastMsg.loading.stage3 = true;
                return { ...prev, messages };
              });
              break;

            case 'stage3_complete':
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                lastMsg.stage3 = event.data;
                lastMsg.loading.stage3 = false;
                lastMsg.streamingStage3 = null;
                return { ...prev, messages };
              });
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
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastMsg = messages[messages.length - 1];
                if (lastMsg?.loading) {
                  lastMsg.loading = { stage1: false, stage2: false, stage3: false };
                }
                return { ...prev, messages };
              });
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
        onOpenSettings={() => setShowSettings(true)}
      />
      <ChatInterface
        conversation={currentConversation}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        mode={mode}
      />
      {showSettings && (
        <Settings
          envConfig={envConfig}
          settings={settings}
          onSave={handleSaveSettings}
          onClear={handleClearSettings}
          onClose={() => setShowSettings(false)}
        />
      )}
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

export default function App() {
  return (
    <Routes>
      <Route path="/ensemble" element={<CouncilPage key="ensemble" mode="ensemble" />} />
      <Route path="/roleplay" element={<CouncilPage key="roleplay" mode="roleplay" />} />
      {/* Заглушка: режим пока не реализован на бэкенде */}
      <Route path="/planner" element={<PlannerStub />} />
      {/* Ролевой режим — основной сценарий, открывается по умолчанию */}
      <Route path="*" element={<Navigate to="/roleplay" replace />} />
    </Routes>
  );
}
