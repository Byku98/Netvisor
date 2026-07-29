interface EdgeDetailsProps {
  /** ID of the edge to display details for. */
  edgeId: string;
}

/** Detail panel for a selected network edge. Currently a placeholder. */
export function EdgeDetails({ edgeId }: EdgeDetailsProps) {
  return (
    <div className="p-4 text-zinc-300">
      <h3 className="font-semibold">Edge Details</h3>
      <p className="text-sm text-zinc-500 mt-1">ID: {edgeId}</p>
    </div>
  );
}
