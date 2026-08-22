import '../styles/ChatInterface.css';

// Заглушка страницы режима: взаимодействие с моделью пока не реализовано
export default function ModeStub({ icon, title, description }) {
  return (
    <div className="chat-interface">
      <div className="empty-state">
        <div className="empty-state-icon">{icon}</div>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
    </div>
  );
}
