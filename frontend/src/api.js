/**
 * API client for the LLM Council backend.
 */

// const API_BASE = 'http://192.168.191.13:8001';
const API_BASE = import.meta.env.VITE_API_BASE || 'http://192.168.191.13:8001';

export const api = {
  /**
   * Get backend config status (whether API key/URL are set in .env).
   */
  async getConfig() {
    const response = await fetch(`${API_BASE}/api/config`);
    if (!response.ok) {
      throw new Error('Failed to get config');
    }
    return response.json();
  },

  /**
   * Create a new conversation.
   * @param {object} device - Optional { device_id, device_name } of the current browser
   */
  async createConversation(device = {}) {
    const response = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(device),
    });
    if (!response.ok) {
      throw new Error('Failed to create conversation');
    }
    return response.json();
  },

  /**
   * Delete a conversation (only allowed from the device that created it).
   * @param {string} conversationId - The conversation ID
   * @param {string} deviceId - The current device ID
   */
  async deleteConversation(conversationId, deviceId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}?device_id=${encodeURIComponent(deviceId)}`,
      {
        method: 'DELETE',
      }
    );
    if (!response.ok) {
      throw new Error('Failed to delete conversation');
    }
    return response.json();
  },

  /**
   * List all conversations.
   */
  async listConversations() {
    const response = await fetch(`${API_BASE}/api/conversations`);
    if (!response.ok) {
      throw new Error('Failed to list conversations');
    }
    return response.json();
  },

  /**
   * Get a specific conversation.
   */
  async getConversation(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}`
    );
    if (!response.ok) {
      throw new Error('Failed to get conversation');
    }
    return response.json();
  },

  /**
   * Send a message in a conversation.
   * @param {string} conversationId - The conversation ID
   * @param {string} content - The message content
   * @param {string} mode - The council mode ('ensemble' or 'roleplay')
   * @param {object} extras - Optional extra fields for the body: { api_key, api_url, device_id, device_name }
   */
  async sendMessage(conversationId, content, mode = 'ensemble', extras = {}) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content, mode, ...extras }),
      }
    );
    if (!response.ok) {
      throw new Error('Failed to send message');
    }
    return response.json();
  },

  /**
   * Send a message and receive streaming updates.
   * @param {string} conversationId - The conversation ID
   * @param {string} content - The message content
   * @param {string} mode - The council mode ('ensemble' or 'roleplay')
   * @param {object} extras - Optional extra fields for the body: { api_key, api_url, device_id, device_name }
   * @param {function} onEvent - Callback function for each event: (eventType, data) => void
   * @returns {Promise<void>}
   */
  async sendMessageStream(conversationId, content, mode, extras, onEvent) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content, mode, ...extras }),
      }
    );

    if (!response.ok) {
      throw new Error('Failed to send message');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      // Декодируем с stream:true, чтобы не разрезать многобайтовые символы
      buffer += decoder.decode(value, { stream: true });

      // События разделяются пустой строкой (\n\n). Накапливаем данные,
      // чтобы большие события (stage1_complete и т.п.), разрезанные на чанки, парсились целиком
      let separator;
      while ((separator = buffer.indexOf('\n\n')) !== -1) {
        const rawEvent = buffer.slice(0, separator).trim();
        buffer = buffer.slice(separator + 2);

        for (const line of rawEvent.split('\n')) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            try {
              const event = JSON.parse(data);
              onEvent(event.type, event);
            } catch (e) {
              console.error('Failed to parse SSE event:', e);
            }
          }
        }
      }
    }
  },
};
