// Iconos SVG propios de EcoConecta: lineales, trazo 2, extremos redondeados,
// rejilla de 24 px. Misma interfaz que se usaba antes (size, strokeWidth,
// className, aria-*), sin bibliotecas de iconos.
const make = (name, body) => {
  function Icon({ size = 24, strokeWidth = 2, className, ...rest }) {
    const labelled = rest["aria-label"] || rest["aria-labelledby"];
    return (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        width={size}
        height={size}
        fill="none"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className ? `icon ${className}` : "icon"}
        focusable="false"
        aria-hidden={labelled ? undefined : "true"}
        role={labelled ? "img" : undefined}
        {...rest}
      >
        {body}
      </svg>
    );
  }
  Icon.displayName = name;
  return Icon;
};

const circle = <circle cx="12" cy="12" r="9" />;

// Navegación y acciones
export const ArrowLeft = make("ArrowLeft", <path d="M19 12H5M11 6l-6 6 6 6" />);
export const ArrowRight = make("ArrowRight", <path d="M5 12h14M13 6l6 6-6 6" />);
export const ChevronDown = make("ChevronDown", <path d="M6 9l6 6 6-6" />);
export const ChevronLeft = make("ChevronLeft", <path d="M15 6l-6 6 6 6" />);
export const ChevronRight = make("ChevronRight", <path d="M9 6l6 6-6 6" />);
export const Check = make("Check", <path d="M5 12.5l4.5 4.5L19 7.5" />);
export const X = make("X", <path d="M6 6l12 12M18 6L6 18" />);
export const Plus = make("Plus", <path d="M12 5v14M5 12h14" />);
export const Search = make("Search", <><circle cx="11" cy="11" r="6.5" /><path d="M20 20l-4.3-4.3" /></>);
export const Send = make("Send", <><path d="M21 3L10.5 13.5" /><path d="M21 3l-6.5 18-4-7.5-7.5-4z" /></>);
export const RotateCcw = make("RotateCcw", <><path d="M3.5 12a8.5 8.5 0 102.6-6.1L3.5 8.5" /><path d="M3.5 3.5v5h5" /></>);
export const LogOut = make("LogOut", <><path d="M9.5 20.5H6a2 2 0 01-2-2v-13a2 2 0 012-2h3.5" /><path d="M15 16.5l4.5-4.5L15 7.5M19.5 12h-10" /></>);
export const Pencil = make("Pencil", <><path d="M4 20h4L19 9a2.8 2.8 0 00-4-4L4 16z" /><path d="M13.5 6.5l4 4" /></>);
export const Edit3 = make("Edit3", <><path d="M4 20h4L18.5 9.5a2.8 2.8 0 00-4-4L4 16z" /><path d="M13 20h7" /></>);
export const Save = make("Save", <><path d="M5 3.5h11l3.5 3.5v12a1.5 1.5 0 01-1.5 1.5H5A1.5 1.5 0 013.5 19V5A1.5 1.5 0 015 3.5z" /><path d="M7.5 3.5v5h8v-5M7.5 20.5v-6h9v6" /></>);
export const Eye = make("Eye", <><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" /><circle cx="12" cy="12" r="3" /></>);
export const EyeOff = make("EyeOff", <path d="M10.6 5.6A9.6 9.6 0 0112 5.5c6 0 9.5 6.5 9.5 6.5a16 16 0 01-2.6 3.4M6.6 6.6C3.9 8.4 2.5 12 2.5 12S6 18.5 12 18.5c1.8 0 3.3-.5 4.6-1.3M9.9 9.9a3 3 0 004.2 4.2M3 3l18 18" />);
export const Menu = make("Menu", <path d="M4 7h16M4 12h16M4 17h16" />);

// Estados y mensajes
export const CircleAlert = make("CircleAlert", <>{circle}<path d="M12 7.5v5.5M12 16.5h.01" /></>);
export const CircleCheck = make("CircleCheck", <>{circle}<path d="M8 12.5l2.7 2.7L16 9.5" /></>);
export const CircleX = make("CircleX", <>{circle}<path d="M9 9l6 6M15 9l-6 6" /></>);
export const CircleHelp = make("CircleHelp", <>{circle}<path d="M9.5 9.5a2.5 2.5 0 114 2c-.9.6-1.5 1.1-1.5 2.2M12 17h.01" /></>);
export const Info = make("Info", <>{circle}<path d="M12 11v5.5M12 7.5h.01" /></>);
export const Clock3 = make("Clock3", <>{circle}<path d="M12 7v5h4" /></>);
export const TriangleAlert = make("TriangleAlert", <><path d="M10.3 4.2L2.7 17.5a2 2 0 001.7 3h15.2a2 2 0 001.7-3L13.7 4.2a2 2 0 00-3.4 0z" /><path d="M12 9.5v4M12 17h.01" /></>);
export const BadgeCheck = make("BadgeCheck", <><path d="M12 2.8l2.3 1.7 2.8-.2.9 2.7 2.3 1.6-.9 2.7.9 2.7-2.3 1.6-.9 2.7-2.8-.2L12 21.2l-2.3-1.7-2.8.2-.9-2.7-2.3-1.6.9-2.7-.9-2.7L6 7.6l.9-2.7 2.8.2z" /><path d="M8.8 12.2l2.2 2.2 4.2-4.3" /></>);
export const ShieldCheck = make("ShieldCheck", <><path d="M12 3l7.5 3v5.5c0 4.6-3.2 8.2-7.5 9.5-4.3-1.3-7.5-4.9-7.5-9.5V6z" /><path d="M8.8 12.2l2.3 2.3 4.2-4.3" /></>);
export const Star = make("Star", <path d="M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1 5.8L12 16.8l-5.2 2.8 1-5.8-4.3-4.1 5.9-.8z" />);

// Personas y cuenta
export const UserRound = make("UserRound", <><circle cx="12" cy="8" r="4" /><path d="M4.5 20.5a7.5 7.5 0 0115 0" /></>);
export const CircleUserRound = make("CircleUserRound", <>{circle}<circle cx="12" cy="10" r="3" /><path d="M6.7 18.4a6 6 0 0110.6 0" /></>);
export const UserPlus = make("UserPlus", <><circle cx="10" cy="8" r="4" /><path d="M3 20.5a7 7 0 0114 0" /><path d="M19 8v6M16 11h6" /></>);
export const UserCog = make("UserCog", <><circle cx="10" cy="8" r="4" /><path d="M3 20.5a7 7 0 0110.5-6" /><circle cx="18" cy="17" r="2.5" /><path d="M18 13v1.5M18 19.5V21M22 17h-1.5M15.5 17H14" /></>);
export const Users = make("Users", <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0113 0" /><path d="M15.5 4.7a3.5 3.5 0 010 6.6M17.5 14a6.5 6.5 0 014 6" /></>);

// Lugares y contacto
export const Home = make("Home", <><path d="M3.5 10.5L12 3.5l8.5 7" /><path d="M5.5 9v11h13V9" /><path d="M10 20v-6h4v6" /></>);
export const House = Home;
export const Building2 = make("Building2", <><path d="M4 21V5.5A1.5 1.5 0 015.5 4h8A1.5 1.5 0 0115 5.5V21" /><path d="M15 10h3.5a1.5 1.5 0 011.5 1.5V21" /><path d="M2.5 21h19M8 8h3M8 12h3M8 16h3" /></>);
export const Store = make("Store", <><path d="M4 10v10h16V10" /><path d="M3 9.5L4.8 4h14.4L21 9.5a2.5 2.5 0 01-5 0 2.5 2.5 0 01-2.5 2.5h-3A2.5 2.5 0 018 9.5a2.5 2.5 0 01-5 0z" /><path d="M10 20v-4.5h4V20" /></>);
export const MapPin = make("MapPin", <><path d="M12 21s-7-6.2-7-11.5a7 7 0 0114 0C19 14.8 12 21 12 21z" /><circle cx="12" cy="9.5" r="2.5" /></>);
export const MapPinned = make("MapPinned", <><path d="M12 17s-5-4.4-5-8.3a5 5 0 0110 0C17 12.6 12 17 12 17z" /><circle cx="12" cy="8.7" r="1.8" /><path d="M7.5 15.5C4.8 16 3 16.9 3 18c0 1.7 4 3 9 3s9-1.3 9-3c0-1.1-1.8-2-4.5-2.5" /></>);
export const MapPinPlus = make("MapPinPlus", <><path d="M19 11c-.6 4.7-7 10-7 10s-7-6.2-7-11.5a7 7 0 0111.2-5.6" /><circle cx="12" cy="9.5" r="2.5" /><path d="M19 2.5v6M16 5.5h6" /></>);
export const Signpost = make("Signpost", <><path d="M12 3v18M9 21h6" /><path d="M5 5.5h12l2.5 2.5L17 10.5H5z" /><path d="M19 13H7l-2.5 2.5L7 18h12z" /></>);
export const Phone = make("Phone", <path d="M5 3.5h3.2l1.6 4.3-2.2 1.5a11 11 0 007.1 7.1l1.5-2.2 4.3 1.6V19a1.5 1.5 0 01-1.6 1.5A16.5 16.5 0 013.5 5.1 1.5 1.5 0 015 3.5z" />);
export const MessageSquare = make("MessageSquare", <path d="M4 5.5A1.5 1.5 0 015.5 4h13A1.5 1.5 0 0120 5.5v10a1.5 1.5 0 01-1.5 1.5H9l-5 4z" />);
export const Bell = make("Bell", <><path d="M6 16v-5a6 6 0 0112 0v5l1.5 2h-15z" /><path d="M10 21h4" /></>);

// Tiempo
export const CalendarDays = make("CalendarDays", <><rect x="3.5" y="5" width="17" height="15.5" rx="2.5" /><path d="M8 3v4M16 3v4M3.5 10h17" /><path d="M8 14h.01M12 14h.01M16 14h.01M8 17.5h.01M12 17.5h.01" /></>);
export const CalendarClock = make("CalendarClock", <><path d="M20.5 11V7.5A2.5 2.5 0 0018 5H6a2.5 2.5 0 00-2.5 2.5V18A2.5 2.5 0 006 20.5h5" /><path d="M8 3v4M16 3v4M3.5 10h17" /><circle cx="17.5" cy="17.5" r="3.5" /><path d="M17.5 16v1.5l1 1" /></>);
export const Sun = make("Sun", <><circle cx="12" cy="12" r="4" /><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" /></>);
export const Sunset = make("Sunset", <><path d="M7.5 16.5a4.5 4.5 0 019 0" /><path d="M2.5 20h19M12 4v6M9 7.5l3 3 3-3" /><path d="M4.5 12.5l1.4 1.4M19.5 12.5l-1.4 1.4M2.5 16.5h2M19.5 16.5h2" /></>);

// Residuos y operación
export const Sprout = make("Sprout", <><path d="M12 21v-9" /><path d="M12 12c0-4 2.5-7 7.5-7 0 4.5-3 7-7.5 7z" /><path d="M12 14c0-3.3-2-5.5-6.5-5.5 0 3.5 2.4 5.5 6.5 5.5z" /></>);
export const Recycle = make("Recycle", <><path d="M7.5 19.5H5a2 2 0 01-1.7-3l2-3.5" /><path d="M10.5 19.5H19a2 2 0 001.7-3l-1.2-2" /><path d="M13 17l-2.5 2.5L13 22" /><path d="M9 8.5l1.3-2.3a2 2 0 013.4 0l2.4 4.2" /><path d="M16.6 7.4l-.5 3.4-3.4-.5" /><path d="M2.5 11.2l2.8 1.8 1.8-2.8" /></>);
export const Truck = make("Truck", <><path d="M2.5 6.5h11v10h-11z" /><path d="M13.5 9.5h4l3 3.5v3.5h-7" /><circle cx="6.5" cy="17.5" r="2" /><circle cx="17" cy="17.5" r="2" /></>);
export const Scale = make("Scale", <><path d="M12 4v16M7 20h10M4 8h16" /><path d="M6.5 8l-3 6.5a3 3 0 006 0zM17.5 8l-3 6.5a3 3 0 006 0z" /></>);
export const Inbox = make("Inbox", <><path d="M3.5 13.5l2.6-7.2A2 2 0 018 5h8a2 2 0 011.9 1.3l2.6 7.2V18a2 2 0 01-2 2h-13a2 2 0 01-2-2z" /><path d="M3.5 13.5H8l1.5 2.5h5l1.5-2.5h4.5" /></>);
export const ClipboardList = make("ClipboardList", <><rect x="5" y="4.5" width="14" height="16.5" rx="2" /><path d="M9 3h6v3H9zM9 11h6M9 15h6" /></>);
export const Ticket = make("Ticket", <><path d="M3.5 7.5A1.5 1.5 0 015 6h14a1.5 1.5 0 011.5 1.5V10a2 2 0 000 4v2.5A1.5 1.5 0 0119 18H5a1.5 1.5 0 01-1.5-1.5V14a2 2 0 000-4z" /><path d="M14 6v2.5M14 11v2M14 15.5V18" /></>);
export const BookOpen = make("BookOpen", <><path d="M3 5.5c2.5-1 6-1 9 1 3-2 6.5-2 9-1V19c-2.5-1-6-1-9 1-3-2-6.5-2-9-1z" /><path d="M12 6.5V20" /></>);
export const History = make("History", <><path d="M3.5 12a8.5 8.5 0 102.6-6.1L3.5 8.5" /><path d="M3.5 3.5v5h5M12 7.5V12l3 2" /></>);
