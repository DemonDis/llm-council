import { useState } from 'react';
import './Settings.css';

export default function Settings({ envConfig, settings, onSave, onClear, onClose }) {
  const [apiKey, setApiKey] = useState(settings.apiKey || '');
  const [apiUrl, setApiUrl] = useState(settings.apiUrl || '');
  const [deviceName, setDeviceName] = useState(settings.deviceName || '');
  const [showKey, setShowKey] = useState(false);
  const [copied, setCopied] = useState(null);

  const keyConfigured = Boolean(envConfig?.api_key_configured);
  const urlConfigured = Boolean(envConfig?.api_url_configured);
  const envUrl = envConfig?.api_url || '';

  const hasLocal = Boolean(settings.apiKey || settings.apiUrl);

  const copy = async (text, label) => {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(label);
      setTimeout(() => setCopied(null), 1500);
    } catch (e) {
      console.error('Copy failed:', e);
    }
  };

  const handleSave = () => {
    onSave({ apiKey: apiKey.trim(), apiUrl: apiUrl.trim(), deviceName: deviceName.trim() });
    onClose();
  };

  const handleReset = () => {
    onClear();
    onClose();
  };

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="settings-header">
          <h3>Настройки API</h3>
          <button className="settings-close" onClick={onClose} aria-label="Закрыть">
            ×
          </button>
        </div>

        <div className="settings-section">
          <label>API-ключ (OPENROUTER_API_KEY)</label>
          <div className="settings-field">
            <input
              type={showKey ? 'text' : 'password'}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={keyConfigured ? 'Оставьте пустым для ключа из .env' : 'sk-or-v1-...'}
              autoComplete="off"
              spellCheck="false"
            />
            <button
              className="settings-btn"
              onClick={() => setShowKey(!showKey)}
              disabled={!apiKey}
              title={showKey ? 'Скрыть ключ' : 'Показать ключ'}
            >
              {showKey ? 'Скрыть' : 'Показать'}
            </button>
            <button
              className="settings-btn"
              onClick={() => copy(apiKey, 'key')}
              disabled={!apiKey}
              title="Копировать ключ"
            >
              {copied === 'key' ? 'Готово' : 'Копировать'}
            </button>
          </div>
          {keyConfigured && (
            <div className="settings-hint">
              Ключ задан в .env. Если поле пустое — используется он. Введите свой ключ, чтобы
              переопределить его.
            </div>
          )}
        </div>

        <div className="settings-section">
          <label>URL API (OPENROUTER_API_URL)</label>
          <div className="settings-field">
            <input
              type="text"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              placeholder="https://openrouter.ai/api/v1/chat/completions"
              spellCheck="false"
            />
            <button
              className="settings-btn"
              onClick={() => copy(apiUrl || envUrl, 'url')}
              disabled={!apiUrl && !envUrl}
              title="Копировать URL"
            >
              {copied === 'url' ? 'Готово' : 'Копировать'}
            </button>
          </div>
          {urlConfigured && (
            <div className="settings-hint">
              URL задан в .env. Если поле пустое — используется он. Введите свой URL, чтобы
              переопределить его.
            </div>
          )}
        </div>

        <div className="settings-section">
          <label>Имя этого устройства</label>
          <div className="settings-field">
            <input
              type="text"
              value={deviceName}
              onChange={(e) => setDeviceName(e.target.value)}
              placeholder="Например: Ноутбук Ивана"
              spellCheck="false"
            />
          </div>
          <div className="settings-hint">
            Будет показываться рядом с вашими разговорами, чтобы другие пользователи видели, с
            какого компьютера они созданы.
          </div>
        </div>

        <div className="settings-actions">
          <button className="settings-save" onClick={handleSave}>
            Сохранить
          </button>
          {hasLocal && (
            <button className="settings-clear" onClick={handleReset}>
              Сбросить к .env
            </button>
          )}
        </div>

        <div className="settings-note">
          Сохранённые значения имеют приоритет над .env и хранятся только в localStorage вашего
          браузера. «Сбросить к .env» удаляет их и возвращает настройки из конфигурации.
        </div>
      </div>
    </div>
  );
}
