import { COMPONENTS, type ComponentId } from "./componentConfig";

interface ComponentDockProps {
  selected: ComponentId;
  onSelect: (id: ComponentId) => void;
}

export function ComponentDock({ selected, onSelect }: ComponentDockProps) {
  return (
    <nav className="component-dock" aria-label="Component dock">
      {COMPONENTS.map((component) => (
        <button
          key={component.id}
          aria-label={`${component.code} ${component.label}`}
          aria-pressed={selected === component.id}
          className={`dock-button ${selected === component.id ? "dock-button--active" : ""}`}
          type="button"
          onClick={() => onSelect(component.id)}
        >
          <span>{component.shortLabel}</span>
          <strong>{component.code}</strong>
        </button>
      ))}
    </nav>
  );
}
