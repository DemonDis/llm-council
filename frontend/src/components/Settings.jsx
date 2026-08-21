import { useState } from 'react';
import './Settings.css';

export default function Settings({ envConfig, settings, onSave, onClear, onClose }) {
  const [apiKey, setApiKey] = useState(settings.apiKey || '');
  const [showKey, setShowKey] = useState(false);
  const [copied, setCopied] = useState(null);

  const keyConfigured = Boolean(envConfig?.api_key_configured);

  const hasLocal = Boolean(settings.apiKey);

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
    onSave({ apiKey: apiKey.trim() });
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
          <label>API-ключ</label>
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
              <div>
              Сохранённые значения имеют приоритет над .env и хранятся только в localStorage вашего
              браузера. «Сбросить к .env» удаляет их и возвращает настройки из конфигурации.
              </div>
            </div>
          )}
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
      </div>
    </div>
  );
}
