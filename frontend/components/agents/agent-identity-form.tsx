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
};

export function AgentIdentityForm({
  name,
  description,
  agentType,
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
        <fieldset disabled className="grid gap-5">
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
                readOnly
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
              readOnly
              aria-describedby="agent-description-description"
            />
          </FormField>
        </fieldset>
        <p className="text-muted-foreground mt-5 text-xs">
          Agent identity is read-only here. Editing will be connected in a
          later update.
        </p>
      </CardContent>
    </Card>
  );
}
