import ReactMarkdown from 'react-markdown';
import './Stage3.css';

function shortName(model) {
  return model.split('/')[1] || model;
}

function ResponseCard({ model, children, streamingLabel }) {
  return (
    <div className="final-response">
      <div className="chairman-label">
        Председатель: {shortName(model)}
        {streamingLabel && <span className="streaming-indicator"> {streamingLabel}</span>}
      </div>
      <div className="final-text markdown-content">
        <ReactMarkdown>{children}</ReactMarkdown>
      </div>
    </div>
  );
}

export default function Stage3({ finalResponse, streamingResponse }) {
  if (finalResponse) {
    return (
      <div className="stage stage3">
        <h3 className="stage-title">Этап 3: Итоговый ответ Совета</h3>
        <p className="stage-description">
          Председатель синтезировал лучшие моменты из всех ответов и рейтингов в итоговое заключение.
        </p>
        <ResponseCard model={finalResponse.model}>
          {finalResponse.response}
        </ResponseCard>
      </div>
    );
  }

  if (streamingResponse) {
    return (
      <div className="stage stage3">
        <h3 className="stage-title">Этап 3: Итоговый ответ Совета</h3>
        <p className="stage-description">
          Председатель синтезирует лучшие моменты из всех ответов и рейтингов…
        </p>
        <ResponseCard
          model={streamingResponse.model}
          streamingLabel={streamingResponse.response.length === 0 ? 'Печатает...' : null}
        >
          {streamingResponse.response || '_Ожидание ответа..._'}
        </ResponseCard>
      </div>
    );
  }

  return null;
}
