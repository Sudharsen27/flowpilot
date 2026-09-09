import { Checkbox } from "@/components/forms/checkbox";
import { Label } from "@/components/forms/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const capabilityConcepts = [
  "Understand enquiries",
  "Qualify leads",
  "Respond to customers",
  "Create or update records",
  "Schedule follow-ups",
  "Escalate to humans",
] as const;

export function AgentCapabilities() {
  return (
    <Card as="section" aria-labelledby="agent-capabilities-title">
      <CardHeader>
        <CardTitle id="agent-capabilities-title">Capabilities</CardTitle>
        <CardDescription>
          Select the business tasks an agent may eventually be configured to
          assist with.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <fieldset disabled>
          <legend className="sr-only">Agent capability configuration</legend>
          <div className="grid gap-3 sm:grid-cols-2">
            {capabilityConcepts.map((capability, index) => {
              const id = `agent-capability-${index}`;
              return (
                <Label
                  key={capability}
                  htmlFor={id}
                  className="border-border bg-surface-subtle flex min-h-12 items-center gap-3 rounded-lg border px-3 py-2.5"
                >
                  <Checkbox id={id} />
                  <span>{capability}</span>
                </Label>
              );
            })}
          </div>
        </fieldset>
        <p className="text-muted-foreground mt-4 text-xs">
          Capability selection is unavailable and does not execute any action.
        </p>
      </CardContent>
    </Card>
  );
}
