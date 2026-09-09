import { StatePanel } from "@/components/data-display/state-panel";

export function QualificationReadiness() {
  return (
    <StatePanel
      kind="unavailable"
      className="max-w-none"
      title="AI qualification is not connected"
      description="Qualification status, scores, and explanations will appear only after the lead data model and AI qualification service are implemented."
    />
  );
}
