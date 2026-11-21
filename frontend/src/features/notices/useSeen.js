import { useCallback, useState } from "react";
import { timestampMillis } from "../../utils/dateTime.js";

// "Nuevo" = aviso posterior a la última vez que esta persona abrió Avisos en
// este dispositivo. La API aún no guarda avisos leídos, así que esto es solo
// local (localStorage, sin datos personales) y no se presenta como sincronizado.
export function useSeen(userId) {
  const key = `eco.notices.seen.${userId}`;
  const read = () => {
    try {
      return Number(localStorage.getItem(key)) || 0;
    } catch {
      return 0;
    }
  };
  const [seenAt, setSeenAt] = useState(read);
  const isNew = useCallback((n) => timestampMillis(n.date) > seenAt, [seenAt]);
  const markSeen = useCallback(() => {
    const now = Date.now();
    try {
      localStorage.setItem(key, String(now));
    } catch {
      /* sin almacenamiento */
    }
    return now;
  }, [key]);
  return { seenAt, setSeenAt, isNew, markSeen };
}
