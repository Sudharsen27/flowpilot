import { FormField } from "@/components/forms/form-field";
import { Textarea } from "@/components/forms/textarea";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export function AgentInstructions() {
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
            description="No instructions are loaded, and this editor does not save changes."
          >
            <Textarea
              id="agent-instructions"
              className="min-h-56 font-mono text-sm"
              placeholder="Instructions will be configured here once agent persistence is available."
              aria-describedby="agent-instructions-description"
            />
          </FormField>
        </fieldset>
      </CardContent>
    </Card>
  );
}
