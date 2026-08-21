import '../styles/ChatInterface.css';

// Заглушка: взаимодействие с моделью для этого режима пока не реализовано
export default function PlannerStub() {
  return (
    <div className="chat-interface">
      <div className="empty-state">
        <div className="empty-state-icon">📋</div>
        <h2>Планировщик команды</h2>
        <p>
          Страница в разработке. Здесь виртуальная команда (продакт, архитектор,
          дизайнер и другие специалисты) будет составлять план по вашей задаче.
        </p>
      </div>
    </div>
  );
}
