import { useId, useState } from 'react';
import { useAdminTranslation } from '../i18n/admin';

// Keep this state in the page when its table unmounts during a query.
export function useTableExpansion() {
  const [expanded, setExpanded] = useState(false);
  return { expanded, toggle: () => setExpanded(value => !value) };
}

export type TableExpansion = ReturnType<typeof useTableExpansion>;

export function useCompactRows<T>(rows: T[], expansion?: TableExpansion) {
  const localExpansion = useTableExpansion();
  const state = expansion ?? localExpansion;
  const bodyId = useId();
  const collapsible = rows.length > 3;
  return {
    ...state,
    bodyId,
    collapsible,
    count: rows.length,
    visibleRows: collapsible && !state.expanded ? rows.slice(0, 3) : rows,
    showPagination: !collapsible || state.expanded,
  };
}

export function CompactTableToggle({
  collapsible, expanded, toggle, bodyId, count,
}: TableExpansion & { collapsible: boolean; bodyId: string; count: number }) {
  const t = useAdminTranslation();
  if (!collapsible) return null;
  return (
    <button
      className="button button-secondary table-toggle"
      type="button"
      aria-expanded={expanded}
      aria-controls={bodyId}
      onClick={toggle}
    >
      {expanded ? t.feedback.collapseRows : t.feedback.showAllRows(count)}
    </button>
  );
}
