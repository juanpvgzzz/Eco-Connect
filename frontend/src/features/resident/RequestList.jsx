import { ClipboardList, Plus } from "../../components/icons.jsx";
import { EmptyState } from "../../components/ui/EmptyState.jsx";
import { Button } from "../../components/ui/Button.jsx";
import { RequestCard } from "./RequestCard.jsx";

export function RequestList({ rows, appointments, freshId, onNew, token }) {
  if (!rows.length)
    return (
      <EmptyState
        icon={ClipboardList}
        title="Aún no tienes solicitudes"
        action={onNew && <Button variant="secondary" icon={Plus} onClick={onNew} className="mt-2">Solicitar mi primera recogida</Button>}
      >
        {onNew && "Pide la recogida de tus residuos orgánicos o reciclables."}
      </EmptyState>
    );
  const byRequest = Object.fromEntries(appointments.map((a) => [a.collection_id, a]));
  return (
    <div className="request-list">
      {rows.map((row) => (
        <RequestCard key={row.id} row={row} appointment={byRequest[row.id]} fresh={row.id === freshId} token={token} />
      ))}
    </div>
  );
}
