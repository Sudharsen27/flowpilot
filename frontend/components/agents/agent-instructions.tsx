import { FormField } from "@/components/forms/form-field";
import { Textarea } from "@/components/forms/textarea";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type AgentInstructionsProps = {
  instructions: string;
  editable: boolean;
  onChange: (value: string) => void;
};

export function AgentInstructions({
  instructions,
  editable,
  onChange,
}: AgentInstructionsProps) {
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
        <fieldset disabled={!editable}>
          <legend className="sr-only">Agent instructions configuration</legend>
          <FormField
            label="Agent instructions"
            htmlFor="agent-instructions"
            description={
              editable
                ? "Changes are saved only when you choose Save configuration."
                : "Your role has read-only access to these instructions."
            }
          >
            <Textarea
              id="agent-instructions"
              className="min-h-56 font-mono text-sm"
              value={instructions}
              onChange={(event) => onChange(event.target.value)}
              maxLength={8000}
              placeholder="No system instructions configured."
              aria-describedby="agent-instructions-description"
            />
          </FormField>
        </fieldset>
      </CardContent>
    </Card>
  );
}
