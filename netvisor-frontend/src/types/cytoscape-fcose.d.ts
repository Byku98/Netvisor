// cytoscape-fcose ships no TypeScript types — declare the extension registration.
declare module "cytoscape-fcose" {
  import type { Ext } from "cytoscape";
  const ext: Ext;
  export default ext;
}
