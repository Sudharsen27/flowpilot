import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Select } from "@/components/forms/select";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { AgentType } from "@/types/api";

type AgentIdentityFormProps = {
  name: string;
  description: string;
  agentType: AgentType;
  editable: boolean;
  onNameChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
  onAgentTypeChange: (value: AgentType) => void;
};

export function AgentIdentityForm({
  name,
  description,
  agentType,
  editable,
  onNameChange,
  onDescriptionChange,
  onAgentTypeChange,
}: AgentIdentityFormProps) {
  return (
    <Card as="section" aria-labelledby="agent-identity-title">
      <CardHeader>
        <CardTitle id="agent-identity-title">Agent identity</CardTitle>
        <CardDescription>
          Define how this agent will be identified and the business purpose it
          will serve.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <fieldset disabled={!editable} className="grid gap-5">
          <legend className="sr-only">Agent identity configuration</legend>
          <div className="grid gap-5 sm:grid-cols-2">
            <FormField
              label="Agent name"
              htmlFor="agent-name"
              description="A clear internal name for the configured agent."
            >
              <Input
                id="agent-name"
                value={name}
                onChange={(event) => onNameChange(event.target.value)}
                minLength={1}
                maxLength={200}
                required
                aria-describedby="agent-name-description"
              />
            </FormField>
            <FormField
              label="Agent type"
              htmlFor="agent-type"
              description="A role concept used to organize configuration."
            >
              <Select
                id="agent-type"
                value={agentType}
                onChange={(event) =>
                  onAgentTypeChange(event.target.value as AgentType)
                }
                aria-describedby="agent-type-description"
              >
                <option value="SALES">Sales</option>
                <option value="SUPPORT">Support</option>
                <option value="OPERATIONS">Operations</option>
                <option value="COMMUNICATION">Communication</option>
              </Select>
            </FormField>
          </div>
          <FormField
            label="Description"
            htmlFor="agent-description"
            description="A concise explanation shown to people managing the agent."
          >
            <Input
              id="agent-description"
              value={description}
              onChange={(event) => onDescriptionChange(event.target.value)}
              maxLength={2000}
              aria-describedby="agent-description-description"
            />
          </FormField>
        </fieldset>
        <p className="text-muted-foreground mt-5 text-xs">
          {editable
            ? "Changes are saved only when you choose Save configuration."
            : "Your role has read-only access to agent configuration."}
        </p>
      </CardContent>
    </Card>
  );
}
