import { StatePanel } from "@/components/data-display/state-panel";

export function QualificationReadiness() {
  return (
    <StatePanel
      kind="unavailable"
      className="max-w-none"
      title="AI qualification is not connected"
      description="Qualification scores and explanations will appear only after the AI qualification service is implemented. Pipeline status on a lead is not an AI score."
    />
  );
}
