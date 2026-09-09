import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Select } from "@/components/forms/select";
import { Textarea } from "@/components/forms/textarea";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export function AgentIdentityForm() {
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
                placeholder="No agent name"
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
                defaultValue=""
                aria-describedby="agent-type-description"
              >
                <option value="">Select agent type</option>
                <option value="sales">Sales</option>
                <option value="support">Support</option>
                <option value="operations">Operations</option>
                <option value="communication">Communication</option>
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
              placeholder="No agent description"
              aria-describedby="agent-description-description"
            />
          </FormField>
          <FormField
            label="Purpose"
            htmlFor="agent-purpose"
            description="The business outcome and boundaries this agent should work within."
          >
            <Textarea
              id="agent-purpose"
              className="min-h-24"
              placeholder="No purpose has been configured."
              aria-describedby="agent-purpose-description"
            />
          </FormField>
        </fieldset>
        <p className="text-muted-foreground mt-5 text-xs">
          Identity controls are unavailable until agent persistence is
          implemented.
        </p>
      </CardContent>
    </Card>
  );
}
