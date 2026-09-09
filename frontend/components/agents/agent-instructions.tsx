import { FormField } from "@/components/forms/form-field";
import { Textarea } from "@/components/forms/textarea";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export function AgentInstructions({ instructions }: { instructions: string }) {
  return (
    <Card as="section" aria-labelledby="agent-instructions-title">
      <CardHeader>
        <CardTitle id="agent-instructions-title">Instructions</CardTitle>
        <CardDescription>
          Instructions will define the agent&apos;s role, operating boundaries,
          priorities, and expected behavior.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <fieldset disabled>
          <legend className="sr-only">Agent instructions configuration</legend>
          <FormField
            label="Agent instructions"
            htmlFor="agent-instructions"
            description="Loaded from the agent record. Editing is not connected yet."
          >
            <Textarea
              id="agent-instructions"
              className="min-h-56 font-mono text-sm"
              value={instructions}
              readOnly
              placeholder="No system instructions configured."
              aria-describedby="agent-instructions-description"
            />
          </FormField>
        </fieldset>
      </CardContent>
    </Card>
  );
}
