import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './Stage2.css';

function shortName(name) {
  return name.split('/')[1] || name;
}

function getDisplayName(rank) {
  return rank.role || shortName(rank.model);
}

function deAnonymizeText(text, labelToModel) {
  if (!labelToModel) return text;

  let result = text;
  // Replace each "Response X" with the actual name (role or model)
  Object.entries(labelToModel).forEach(([label, name]) => {
    const displayName = shortName(name);
    result = result.replace(new RegExp(label, 'g'), `**${displayName}**`);
  });
  return result;
}

export default function Stage2({ rankings, labelToModel, aggregateRankings, mode }) {
  const [activeTab, setActiveTab] = useState(0);

  if (!rankings || rankings.length === 0) {
    return null;
  }

  const isRoleplay = mode === 'roleplay';

  return (
    <div className="stage stage2">
      <h3 className="stage-title">Этап 2: Взаимные рейтинги</h3>

      <h4>Сырые оценки</h4>
      <p className="stage-description">
        {isRoleplay
          ? 'Каждая роль оценила все ответы (анонимизированы как Response A, B, C и т.д.) и предоставила рейтинг. Ниже имена ролей показаны жирным для читаемости, но исходная оценка использовала анонимные метки.'
          : 'Каждая модель оценила все ответы (анонимизированы как Response A, B, C и т.д.) и предоставила рейтинг. Ниже названия моделей показаны жирным для читаемости, но исходная оценка использовала анонимные метки.'}
      </p>

      <div className="tabs">
        {rankings.map((rank, index) => (
          <button
            key={index}
            className={`tab ${activeTab === index ? 'active' : ''}`}
            onClick={() => setActiveTab(index)}
          >
            {getDisplayName(rank)}
          </button>
        ))}
      </div>

      <div className="tab-content">
        <div className="ranking-model">{getDisplayName(rankings[activeTab])}</div>
        <div className="ranking-content markdown-content">
          <ReactMarkdown>
            {deAnonymizeText(rankings[activeTab].ranking, labelToModel)}
          </ReactMarkdown>
        </div>

        {rankings[activeTab].parsed_ranking &&
         rankings[activeTab].parsed_ranking.length > 0 && (
          <div className="parsed-ranking">
            <strong>Извлечённый рейтинг:</strong>
            <ol>
              {rankings[activeTab].parsed_ranking.map((label, i) => (
                <li key={i}>
                  {labelToModel && labelToModel[label]
                    ? shortName(labelToModel[label])
                    : label}
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>

      {aggregateRankings && aggregateRankings.length > 0 && (
        <div className="aggregate-rankings">
          <h4>Агрегированные рейтинги</h4>
          <p className="stage-description">
            Суммарные результаты по всем взаимным оценкам (меньше баллов — лучше):
          </p>
          <div className="aggregate-list">
            {aggregateRankings.map((agg, index) => (
              <div key={index} className="aggregate-item">
                <span className="rank-position">#{index + 1}</span>
                <span className="rank-model">{shortName(agg.model)}</span>
                <span className="rank-score">
                  Среднее: {agg.average_rank.toFixed(2)}
                </span>
                <span className="rank-count">
                  ({agg.rankings_count} голосов)
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
