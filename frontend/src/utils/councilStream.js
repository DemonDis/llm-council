/**
 * Модульный стор потоковой генерации, независимый от жизненного цикла React.
 *
 * Стримы живут на уровне модуля: переход в другой чат, переключение страницы
 * (ensemble ↔ roleplay) или перезагрузка компонента не прерывают загрузку —
 * вернувшись, подписчик видит актуальный прогресс. После перезагрузки
 * страницы стор переподключается к фоновой задаче бэкенда через
 * api.getMessageEvents() и добирает пропущенные события.
 *
 * Снапшот для UI:
 *   {
 *     status: 'streaming' | 'complete' | 'error',
 *     userMessage: { role: 'user', content } | null,
 *     draftMessage: <assistant message> | null,
 *   }
 */

import { api } from './api';

const streams = new Map();

function createDraft(fromStored = null) {
  return {
    role: 'assistant',
    status: fromStored?.status || 'pending',
    content: fromStored?.content || null,
    stage1: fromStored?.stage1 || null,
    stage2: fromStored?.stage2 || null,
    stage3: fromStored?.stage3 || null,
    metadata: fromStored?.metadata || null,
    streamingReply: null,
    streamingSlots: {},
    streamingSlotsStage2: {},
    streamingStage3: null,
    rolesTotal: 0,
    activeRoleIndex: -1,
    activeRoleIndexStage2: -1,
    loading: {
      reply: false,
      stage1: false,
      stage2: false,
      stage3: false,
    },
  };
}

/**
 * Применяет событие стрима к черновику сообщения.
 * Возвращает новый объект (React должен видеть смену ссылки).
 */
function applyEvent(prev, eventType, event) {
  const m = {
    ...prev,
    loading: { ...prev.loading },
    streamingSlots: { ...prev.streamingSlots },
    streamingSlotsStage2: { ...prev.streamingSlotsStage2 },
    streamingStage3: prev.streamingStage3 ? { ...prev.streamingStage3 } : null,
  };

  switch (eventType) {
    case 'reply_start':
      m.loading.reply = true;
      break;

    case 'reply_chunk':
      m.streamingReply = (m.streamingReply || '') + event.content;
      break;

    case 'reply_complete':
      m.content = event.data?.response ?? m.streamingReply;
      m.streamingReply = null;
      m.loading.reply = false;
      break;

    case 'stage1_start':
      m.loading.stage1 = true;
      m.rolesTotal = event.roles_total || m.rolesTotal;
      break;

    case 'stage1_role_start':
      m.streamingSlots[event.index] = { role: event.role, response: '' };
      break;

    case 'stage1_role_active':
      m.activeRoleIndex = event.index;
      break;

    case 'stage1_chunk': {
      const slot = m.streamingSlots[event.index];
      if (slot) {
        m.streamingSlots[event.index] = { ...slot, response: slot.response + event.content };
      }
      break;
    }

    case 'stage1_complete':
      m.stage1 = event.data;
      m.loading.stage1 = false;
      m.streamingSlots = {};
      m.activeRoleIndex = -1;
      break;

    case 'stage2_start':
      m.loading.stage2 = true;
      break;

    case 'stage2_role_start':
      m.streamingSlotsStage2[event.index] = { role: event.role, ranking: '' };
      break;

    case 'stage2_role_active':
      m.activeRoleIndexStage2 = event.index;
      break;

    case 'stage2_chunk': {
      const slot = m.streamingSlotsStage2[event.index];
      if (slot) {
        m.streamingSlotsStage2[event.index] = { ...slot, ranking: slot.ranking + event.content };
      }
      break;
    }

    case 'stage2_complete':
      m.stage2 = event.data;
      m.metadata = event.metadata;
      m.loading.stage2 = false;
      m.streamingSlotsStage2 = {};
      m.activeRoleIndexStage2 = -1;
      break;

    case 'stage3_start':
      m.loading.stage3 = true;
      break;

    case 'stage3_role_start':
      m.streamingStage3 = { model: event.model, response: '' };
      break;

    case 'stage3_chunk':
      if (m.streamingStage3) {
        m.streamingStage3 = { ...m.streamingStage3, response: m.streamingStage3.response + event.content };
      }
      break;

    case 'stage3_complete':
      m.stage3 = event.data;
      m.loading.stage3 = false;
      m.streamingStage3 = null;
      break;

    default:
      break;
  }

  return m;
}

/** Остановить индикаторы загрузки (при ошибке стрима частичные данные остаются). */
function stopLoading(m) {
  m.loading = { reply: false, stage1: false, stage2: false, stage3: false };
  m.activeRoleIndex = -1;
  m.activeRoleIndexStage2 = -1;
  return m;
}

function getState(conversationId) {
  let st = streams.get(conversationId);
  if (!st) {
    st = { status: 'idle', userContent: null, draft: null, listeners: new Set(), pendingRefetch: false };
    streams.set(conversationId, st);
  }
  return st;
}

function snapshot(st) {
  if (st.status === 'idle') return null;
  return {
    status: st.status,
    userMessage: st.userContent != null ? { role: 'user', content: st.userContent } : null,
    draftMessage: st.draft,
  };
}

function notify(conversationId) {
  const st = streams.get(conversationId);
  if (!st) return;
  const snap = snapshot(st);
  for (const listener of st.listeners) listener(snap);
}

/**
 * Подписка на изменения стрима разговора. Возвращает функцию отписки.
 */
export function subscribe(conversationId, listener) {
  const st = getState(conversationId);
  st.listeners.add(listener);
  listener(snapshot(st));
  return () => st.listeners.delete(listener);
}

export function getSnapshot(conversationId) {
  const st = streams.get(conversationId);
  return st ? snapshot(st) : null;
}

export function isStreaming(conversationId) {
  const st = streams.get(conversationId);
  return !!st && st.status === 'streaming';
}

/**
 * Убрать оверлей (вызывается после того, как свежие данные загружены
 * из хранилища и дубликаты больше не нужны).
 *
 * ВАЖНО: запись сбрасывается в idle, но НЕ удаляется — вместе с записью
 * удалился бы Set подписчиков, и компоненты, подписанные через subscribe(),
 * перестали бы получать события следующего стрима этого разговора
 * (симптом: второе сообщение «не стримится», а по завершении дублируется
 * предыдущий обмен).
 */
export function clear(conversationId) {
  if (isStreaming(conversationId)) return; // активный стрим не трогаем
  const st = streams.get(conversationId);
  if (!st) return;
  st.status = 'idle';
  st.userContent = null;
  st.draft = null;
  notify(conversationId); // подписчики получают null — оверлей снят
  if (st.listeners.size === 0) streams.delete(conversationId);
}

/**
 * Общий цикл обработки событий для sendMessage и attachToMessage.
 */
async function runEventLoop(conversationId, streamPromise, hooks = {}) {
  const st = streams.get(conversationId);
  try {
    await streamPromise;
    st.status = st.status === 'streaming' ? 'complete' : st.status;
  } catch (error) {
    console.error('Stream failed:', error);
    // Частичные результаты могли уже сохраниться на бэкенде — помечаем ошибку,
    // но черновик оставляем: пользователь увидит то, что успело прийти.
    if (st.status === 'streaming') {
      st.status = 'error';
      st.draft = stopLoading({ ...st.draft });
    }
  } finally {
    notify(conversationId);
    hooks.onFinished?.(conversationId, st.status);
  }
}

function handleCouncilEvent(conversationId, eventType, event, hooks) {
  const st = streams.get(conversationId);
  if (!st || !st.draft) return;

  if (eventType === 'title_complete') {
    hooks.onTitleComplete?.();
    return;
  }
  if (eventType === 'complete') {
    hooks.onComplete?.();
    return;
  }
  if (eventType === 'error') {
    console.error('Stream error:', event.message);
    st.draft = stopLoading(applyEvent(st.draft, 'error', event));
    return;
  }

  st.draft = applyEvent(st.draft, eventType, event);
  notify(conversationId);
}

/**
 * Отправить сообщение. Стрим продолжается даже если все компоненты
 * отписались (пользователь ушёл в другой чат/на другую страницу).
 */
export function sendMessage(conversationId, content, mode, credentials, hooks = {}) {
  if (isStreaming(conversationId)) {
    throw new Error('Generation already in progress for this conversation');
  }

  const st = getState(conversationId);
  st.status = 'streaming';
  st.userContent = content;
  st.draft = createDraft();

  const streamPromise = api.sendMessageStream(
    conversationId,
    content,
    mode,
    credentials,
    (eventType, event) => handleCouncilEvent(conversationId, eventType, event, hooks)
  );

  notify(conversationId);
  return runEventLoop(conversationId, streamPromise, hooks);
}

/**
 * Переподключиться к генерации сообщения после перезагрузки страницы.
 *
 * Черновик инициализируется тем, что уже сохранено на бэкенде, а недостающие
 * события приходят из буфера фоновой задачи (или мгновенным replay).
 */
export async function attachToMessage(conversationId, messageIndex, storedMessage, hooks = {}) {
  if (isStreaming(conversationId)) return; // уже подключены через sendMessage

  const st = getState(conversationId);
  st.status = 'streaming';
  st.userContent = null;
  st.draft = createDraft(storedMessage);

  const streamPromise = api.getMessageEvents(
    conversationId,
    messageIndex,
    (eventType, event) => handleCouncilEvent(conversationId, eventType, event, hooks)
  );

  notify(conversationId);
  return runEventLoop(conversationId, streamPromise, hooks);
}
