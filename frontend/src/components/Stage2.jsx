import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import '../styles/Stage2.css';

function shortName(name) {
  return name.split('/')[1] || name;
}

function getDisplayName(rank) {
  return rank.role || shortName(rank.model);
}

function deAnonymizeText(text, labelToModel) {
  if (!labelToModel) return text;

  let result = text;
  Object.entries(labelToModel).forEach(([label, name]) => {
    const displayName = shortName(name);
    result = result.replace(new RegExp(label, 'g'), `**${displayName}**`);
  });
  return result;
}

function RankingTabs({ items, activeTab, onTabClick, loadingIndices }) {
  return (
    <div className="tabs">
      {items.map((item, index) => (
        <button
          key={index}
          className={`tab ${activeTab === index ? 'active' : ''}`}
          onClick={() => onTabClick(index)}
        >
          {item.label}
          {item.loading && <span className="tab-loading-indicator"> ...</span>}
        </button>
      ))}
    </div>
  );
}

function RankingViewer({ name, content, placeholder, streamingLabel }) {
  return (
    <div className="tab-content">
      <div className="ranking-model">
        {name}
        {streamingLabel && <span className="streaming-indicator"> {streamingLabel}</span>}
      </div>
      <div className="ranking-content markdown-content">
        <ReactMarkdown>{content || placeholder}</ReactMarkdown>
      </div>
    </div>
  );
}

function ParsedRanking({ parsedRanking, labelToModel }) {
  if (!parsedRanking || parsedRanking.length === 0) return null;

  return (
    <div className="parsed-ranking">
      <div className="parsed-ranking-label">Извлечённый рейтинг</div>
      <ol>
        {parsedRanking.map((label, i) => (
          <li key={i}>
            {labelToModel && labelToModel[label]
              ? shortName(labelToModel[label])
              : label}
          </li>
        ))}
      </ol>
    </div>
  );
}

function AggregateRankings({ rankings }) {
  if (!rankings || rankings.length === 0) return null;

  return (
    <div className="aggregate-rankings">
      <div className="aggregate-header">Агрегированные рейтинги</div>
      <p className="aggregate-description">
        Суммарные результаты по всем взаимным оценкам (меньше баллов — лучше)
      </p>
      <div className="aggregate-list">
        {rankings.map((agg, index) => (
          <div key={index} className={`aggregate-item ${index === 0 ? 'aggregate-item--first' : ''}`}>
            <span className="rank-position">#{index + 1}</span>
            <span className="rank-model">{shortName(agg.model)}</span>
            <span className="rank-score">
              {agg.average_rank.toFixed(2)}
            </span>
            <span className="rank-count">
              {agg.rankings_count} голосов
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Stage2({ rankings, labelToModel, aggregateRankings, mode, streamingSlots, rolesTotal }) {
  const [activeTab, setActiveTab] = useState(0);

  const isStreaming = !rankings && streamingSlots && Object.keys(streamingSlots).length > 0;
  const slots = streamingSlots || {};
  const slotIndices = Object.keys(slots).map(Number).sort((a, b) => a - b);

  useEffect(() => {
    if (isStreaming && slotIndices.length > 0) {
      setActiveTab(slotIndices[slotIndices.length - 1]);
    }
  }, [isStreaming, slotIndices.length]);

  const isRoleplay = mode === 'roleplay';
  const description = isRoleplay
    ? 'Каждая роль оценила анонимизированные ответы (Response A, B, C …) и проранжировала их. Имена ролей показаны жирным для читаемости — исходная оценка использовала анонимные метки.'
    : 'Каждая модель оценила анонимизированные ответы (Response A, B, C …) и проранжировала их. Названия моделей показаны жирным для читаемости — исходная оценка использовала анонимные метки.';

  // Final results view
  if (rankings && rankings.length > 0) {
    const current = rankings[activeTab];
    const parsedRanking = current?.parsed_ranking;

    return (
      <div className="stage stage2">
        <h3 className="stage-title">Этап 2: Взаимные рейтинги</h3>
        <p className="stage-description">{description}</p>

        <RankingTabs
          items={rankings.map((r) => ({ label: getDisplayName(r) }))}
          activeTab={activeTab}
          onTabClick={setActiveTab}
        />
        <RankingViewer
          name={getDisplayName(current)}
          content={deAnonymizeText(current.ranking, labelToModel)}
        />
        <ParsedRanking parsedRanking={parsedRanking} labelToModel={labelToModel} />
        <AggregateRankings rankings={aggregateRankings} />
      </div>
    );
  }

  // Streaming view
  if (!isStreaming) return null;

  const currentSlot = slots[activeTab];

  return (
    <div className="stage stage2">
      <h3 className="stage-title">Этап 2: Взаимные рейтинги</h3>
      <p className="stage-description">{description}</p>

      <RankingTabs
        items={slotIndices.map((i) => ({
          label: slots[i].role,
          loading: slots[i].ranking.length === 0,
        }))}
        activeTab={activeTab}
        onTabClick={setActiveTab}
      />
      {currentSlot && (
        <RankingViewer
          name={currentSlot.role}
          content={currentSlot.ranking}
          placeholder="_Ожидание оценки..._"
          streamingLabel={currentSlot.ranking.length === 0 ? 'Печатает...' : null}
        />
      )}
    </div>
  );
}
