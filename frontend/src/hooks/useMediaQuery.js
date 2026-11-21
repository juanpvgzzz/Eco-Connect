import { useEffect, useState } from "react";

// Devuelve true mientras la consulta CSS se cumpla (p. ej. tableta horizontal).
export function useMediaQuery(query) {
  const get = () => typeof window !== "undefined" && window.matchMedia?.(query).matches;
  const [matches, setMatches] = useState(get);
  useEffect(() => {
    const list = window.matchMedia?.(query);
    if (!list) return;
    const update = () => setMatches(list.matches);
    update();
    list.addEventListener("change", update);
    return () => list.removeEventListener("change", update);
  }, [query]);
  return Boolean(matches);
}
