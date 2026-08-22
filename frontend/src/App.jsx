import { useState, useEffect, useMemo, useRef } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { Sidebar, ChatInterface, LeaderPicker, StaffPicker, Settings, ConfirmDialog } from './components';
import { api, councilStream } from './utils';
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

// Собирает отображаемый разговор: данные бэкенда + оверлей активного стрима.
// Оверлей живёт в модульном сторе, поэтому переживает смену чата/страницы.
// Если хвост сохранённых сообщений совпадает с оверлеем (стрим уже сохранён
// на бэкенде), дубликат убираем — иначе после обновления было бы двоение.
function buildDisplayConversation(base, overlay) {
  if (!base) return base;
  if (!overlay) return base;

  const extra = [];
  if (overlay.userMessage) extra.push(overlay.userMessage);
  if (overlay.draftMessage) extra.push(overlay.draftMessage);
  if (extra.length === 0) return base;

  let messages = base.messages;

  if (overlay.userMessage && messages.length >= 2) {
    const lastUser = messages[messages.length - 2];
    const lastMsg = messages[messages.length - 1];
    if (
      lastUser?.role === 'user' &&
      lastUser.content === overlay.userMessage.content &&
      lastMsg?.role === 'assistant'
    ) {
      messages = messages.slice(0, -2);
    }
  } else if (!overlay.userMessage && messages.length >= 1) {
    // Переподключение: черновик заменяет собой заглушку из хранилища
    const lastMsg = messages[messages.length - 1];
    if (lastMsg?.role === 'assistant') {
      messages = messages.slice(0, -1);
    }
  }

  return { ...base, messages: [...messages, ...extra] };
}

function CouncilPage({ mode, deviceId, settings, onOpenSettings, setup }) {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [streamOverlay, setStreamOverlay] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Актуальный id для колбэков стрима (они живут дольше рендера)
  const currentIdRef = useRef(null);
  useEffect(() => {
    currentIdRef.current = currentConversationId;
  }, [currentConversationId]);

  // Подписка на состояние стрима выбранного разговора.
  // Стрим продолжается в сторе даже после ухода со страницы.
  useEffect(() => {
    if (!currentConversationId) {
      setStreamOverlay(null);
      return;
    }
    return councilStream.subscribe(currentConversationId, setStreamOverlay);
  }, [currentConversationId]);

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

  const finishStream = async (conversationId) => {
    loadConversations();
    if (conversationId === currentIdRef.current) {
      try {
        const conv = await api.getConversation(conversationId);
        setCurrentConversation(conv);
      } catch (error) {
        console.error('Failed to reload conversation:', error);
      }
    }
    // Оверлей больше не нужен — все данные уже в currentConversation
    councilStream.clear(conversationId);
  };

  const loadConversation = async (id) => {
    try {
      const conv = await api.getConversation(id);
      setCurrentConversation(conv);

      // Если последнее сообщение ассистента всё ещё генерируется
      // (например, страница была перезагружена) — переподключаемся к фоновой
      // задаче и добираем пропущенные события.
      const messages = conv?.messages || [];
      const last = messages[messages.length - 1];
      if (last?.role === 'assistant' && last.status === 'pending') {
        councilStream.attachToMessage(id, messages.length - 1, last, {
          onTitleComplete: loadConversations,
          onFinished: finishStream,
        }).catch((error) => console.error('Failed to attach to stream:', error));
      }
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  // Обычные режимы: кнопка сразу создаёт разговор.
  // Режимы с выбором участника (setup): возвращает к экрану выбора.
  const handleNewConversation = async () => {
    if (setup) {
      setCurrentConversationId(null);
      setCurrentConversation(null);
      return;
    }
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

  // Режимы с выбором участников: диалог — один руководитель (объект),
  // штаб — массив выбранных сотрудников
  const handleStartWithProfiles = async (members) => {
    if (!setup) return;
    const list = Array.isArray(members) ? members : [members];
    try {
      const payload = { device_id: deviceId, mode };
      if (mode === 'staff') {
        payload.profile_ids = list.map((m) => m.id);
      } else {
        payload.profile_id = list[0].id;
        payload.profile_name = list[0].name;
      }
      const newConv = await api.createConversation(payload);
      setConversations((prev) => [
        {
          id: newConv.id,
          created_at: newConv.created_at,
          mode: newConv.mode,
          message_count: 0,
          device_id: deviceId,
        },
        ...prev.filter((c) => c.id !== newConv.id),
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
      // Если по разговору шла генерация — убираем её оверлей
      if (!councilStream.isStreaming(id)) {
        councilStream.clear(id);
      }
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

  const handleSendMessage = (content) => {
    if (!currentConversationId) return;
    if (councilStream.isStreaming(currentConversationId)) return;

    try {
      councilStream.sendMessage(
        currentConversationId,
        content,
        mode,
        credentials,
        {
          onTitleComplete: loadConversations,
          onFinished: finishStream,
        }
      );
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  };

  const isStreamingCurrent = streamOverlay?.status === 'streaming';
  const displayConversation = useMemo(
    () => buildDisplayConversation(currentConversation, streamOverlay),
    [currentConversation, streamOverlay]
  );
  const showSetup = !!setup && !currentConversationId;

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={showSetup ? null : handleNewConversation}
        onDeleteConversation={setDeleteTarget}
        onOpenSettings={onOpenSettings}
      />
      {setup && currentConversationId === null ? (
        <setup.Screen onStart={(members) => handleStartWithProfiles(members)} />
      ) : (
        <ChatInterface
          conversation={displayConversation}
          onSendMessage={handleSendMessage}
          isLoading={isStreamingCurrent}
          mode={mode}
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
        {/* Диалог с руководителем: сначала выбор участника, затем чат с ним */}
        <Route
          path="/dialogue"
          element={
            <CouncilPage
              key="dialogue"
              mode="dialogue"
              deviceId={deviceId}
              settings={settings}
              onOpenSettings={openSettings}
              setup={{ Screen: LeaderPicker }}
            />
          }
        />
        {/* Командный штаб: выбор нескольких офицеров, затем совещание */}
        <Route
          path="/staff"
          element={
            <CouncilPage
              key="staff"
              mode="staff"
              deviceId={deviceId}
              settings={settings}
              onOpenSettings={openSettings}
              setup={{ Screen: StaffPicker }}
            />
          }
        />
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
