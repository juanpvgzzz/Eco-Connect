// Une clases CSS ignorando valores falsos.
export const cx = (...names) => names.filter(Boolean).join(" ");
