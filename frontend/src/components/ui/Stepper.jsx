// Indicador de pasos. Los pasos ya completados se pueden revisitar.
export function Stepper({ steps, current, onStep, label = "Progreso" }) {
  return (
    <nav aria-label={label}>
      <ol className="stepper">
        {steps.map((title, index) => {
          const state = index < current ? "done" : index === current ? "current" : "next";
          return (
            <li key={title} className="step" data-state={state}>
              <span className="step-bar" aria-hidden="true" />
              <button
                type="button"
                className="step-button"
                disabled={index >= current || !onStep}
                aria-current={state === "current" ? "step" : undefined}
                onClick={() => onStep?.(index)}
              >
                <span className="step-num" aria-hidden="true">{index + 1}</span>
                <span>
                  <span className="visually-hidden">Paso {index + 1} de {steps.length}: </span>
                  {title}
                  {state === "done" && <span className="visually-hidden"> (completado)</span>}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
