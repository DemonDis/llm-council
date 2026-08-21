import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import './Stage1.css';

function getDisplayName(resp) {
  return resp.role || resp.model.split('/')[1] || resp.model;
}

function TabBar({ items, activeTab, onTabClick, loadingIndices }) {
  return (
    <div className="tabs">
      {items.map((item, index) => (
        <button
          key={index}
          className={`tab ${activeTab === index ? 'active' : ''}`}
          onClick={() => onTabClick(index)}
        >
          {item.label}
          {loadingIndices?.has(index) && (
            <span className="tab-loading-indicator"> ...</span>
          )}
        </button>
      ))}
    </div>
  );
}

function TabContent({ name, detail, response, placeholder }) {
  return (
    <div className="tab-content">
      <div className="model-name">
        {name}
        {detail && <span className="model-detail"> — {detail}</span>}
      </div>
      <div className="response-text markdown-content">
        <ReactMarkdown>{response || placeholder}</ReactMarkdown>
      </div>
    </div>
  );
}

export default function Stage1({ responses, streamingSlots }) {
  const [activeTab, setActiveTab] = useState(0);

  const isStreaming = !responses && streamingSlots && Object.keys(streamingSlots).length > 0;
  const slots = streamingSlots || {};
  const slotIndices = Object.keys(slots).map(Number).sort((a, b) => a - b);

  useEffect(() => {
    if (isStreaming && slotIndices.length > 0) {
      setActiveTab(slotIndices[slotIndices.length - 1]);
    }
  }, [isStreaming, slotIndices.length]);

  if (responses && responses.length > 0) {
    const current = responses[activeTab];
    return (
      <div className="stage stage1">
        <h3 className="stage-title">Этап 1: Индивидуальные ответы</h3>
        <TabBar
          items={responses.map((r) => ({ label: getDisplayName(r) }))}
          activeTab={activeTab}
          onTabClick={setActiveTab}
        />
        <TabContent
          name={getDisplayName(current)}
          detail={current.role ? current.model : null}
          response={current.response}
        />
      </div>
    );
  }

  if (!isStreaming) return null;

  const loadingIndices = new Set(
    slotIndices.filter((i) => slots[i].response.length === 0)
  );
  const currentSlot = slots[activeTab];

  return (
    <div className="stage stage1">
      <h3 className="stage-title">Этап 1: Индивидуальные ответы</h3>
      <TabBar
        items={slotIndices.map((i) => ({ label: slots[i].role }))}
        activeTab={activeTab}
        onTabClick={setActiveTab}
        loadingIndices={loadingIndices}
      />
      {currentSlot && (
        <TabContent
          name={currentSlot.role}
          response={currentSlot.response}
          placeholder="_Ожидание ответа..._"
        />
      )}
    </div>
  );
}
