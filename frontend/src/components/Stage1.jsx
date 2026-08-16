import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './Stage1.css';

function getDisplayName(resp) {
  return resp.role || resp.model.split('/')[1] || resp.model;
}

export default function Stage1({ responses }) {
  const [activeTab, setActiveTab] = useState(0);

  if (!responses || responses.length === 0) {
    return null;
  }

  return (
    <div className="stage stage1">
      <h3 className="stage-title">Этап 1: Индивидуальные ответы</h3>

      <div className="tabs">
        {responses.map((resp, index) => (
          <button
            key={index}
            className={`tab ${activeTab === index ? 'active' : ''}`}
            onClick={() => setActiveTab(index)}
          >
            {getDisplayName(resp)}
          </button>
        ))}
      </div>

      <div className="tab-content">
        <div className="model-name">
          {getDisplayName(responses[activeTab])}
          {responses[activeTab].role && (
            <span className="model-detail">
              {' '}
              — {responses[activeTab].model}
            </span>
          )}
        </div>
        <div className="response-text markdown-content">
          <ReactMarkdown>{responses[activeTab].response}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
