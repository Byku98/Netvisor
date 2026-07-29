interface NodeDetailsProps {
  /** ID of the node to display details for. */
  nodeId: string;
}

/** Detail panel for a selected network node. Currently a placeholder. */
export function NodeDetails({ nodeId }: NodeDetailsProps) {
  return (
    <div className="p-4 text-zinc-300">
      <h3 className="font-semibold">Node Details</h3>
      <p className="text-sm text-zinc-500 mt-1">ID: {nodeId}</p>
    </div>
  );
}
