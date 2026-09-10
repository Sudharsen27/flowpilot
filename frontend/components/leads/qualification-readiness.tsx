import { StatePanel } from "@/components/data-display/state-panel";

export function QualificationReadiness() {
  return (
    <StatePanel
      kind="information"
      className="max-w-none"
      title="AI qualification is an analysis, not CRM status"
      description="Use Analyze with AI on a lead to extract intent, missing information, and a qualification judgment from an enquiry. The lead's pipeline status does not change automatically. Model confidence is self-reported and not a calibrated probability."
    />
  );
}
