import { Label } from "@/components/forms/label";
import { Switch } from "@/components/forms/switch";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const safetyPolicies = [
  {
    id: "approval-sensitive-actions",
    label: "Require approval for sensitive actions",
    description: "Pause sensitive work for a person to review.",
  },
  {
    id: "escalate-uncertain-conversations",
    label: "Escalate uncertain conversations",
    description: "Surface conversations when confidence is insufficient.",
  },
  {
    id: "automatic-customer-responses",
    label: "Allow automatic customer responses",
    description: "Permit responses without an individual review step.",
  },
  {
    id: "approval-external-actions",
    label: "Require approval before external actions",
    description: "Review work before it changes an external system.",
  },
] as const;

export function AgentSafety() {
  return (
    <Card as="section" aria-labelledby="agent-safety-title">
      <CardHeader>
        <CardTitle id="agent-safety-title">Human approval and safety</CardTitle>
        <CardDescription>
          Future control policies for decisions that should require human
          oversight.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <fieldset disabled>
          <legend className="sr-only">Agent safety policy configuration</legend>
          <div className="divide-border divide-y">
            {safetyPolicies.map((policy) => (
              <div
                key={policy.id}
                className="flex items-start justify-between gap-4 py-4 first:pt-0 last:pb-0"
              >
                <div>
                  <Label htmlFor={policy.id}>{policy.label}</Label>
                  <p className="text-muted-foreground mt-1 text-xs leading-5">
                    {policy.description}
                  </p>
                </div>
                <Switch id={policy.id} checked={false} disabled />
              </div>
            ))}
          </div>
        </fieldset>
        <p className="text-muted-foreground mt-5 text-xs">
          No safety policy is configured or enforced in this UI foundation.
        </p>
      </CardContent>
    </Card>
  );
}
