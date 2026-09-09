import { FormField } from "@/components/forms/form-field";
import { Select } from "@/components/forms/select";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export function AgentCommunication() {
  return (
    <Card as="section" aria-labelledby="agent-communication-title">
      <CardHeader>
        <CardTitle id="agent-communication-title">
          Communication behavior
        </CardTitle>
        <CardDescription>
          Future settings for how an agent communicates and transitions work to
          a person.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <fieldset disabled className="grid gap-5 sm:grid-cols-2">
          <legend className="sr-only">Agent communication configuration</legend>
          <FormField label="Tone" htmlFor="agent-tone">
            <Select id="agent-tone" defaultValue="">
              <option value="">Not configured</option>
              <option value="professional">Professional</option>
              <option value="friendly">Friendly</option>
              <option value="concise">Concise</option>
            </Select>
          </FormField>
          <FormField label="Response style" htmlFor="agent-response-style">
            <Select id="agent-response-style" defaultValue="">
              <option value="">Not configured</option>
              <option value="brief">Brief</option>
              <option value="balanced">Balanced</option>
              <option value="detailed">Detailed</option>
            </Select>
          </FormField>
          <FormField
            label="Business-hours behavior"
            htmlFor="agent-business-hours"
          >
            <Select id="agent-business-hours" defaultValue="">
              <option value="">Not configured</option>
              <option value="wait">Wait for business hours</option>
              <option value="acknowledge">Prepare an acknowledgement</option>
              <option value="handoff">Request human handoff</option>
            </Select>
          </FormField>
          <FormField label="Human-handoff behavior" htmlFor="agent-handoff">
            <Select id="agent-handoff" defaultValue="">
              <option value="">Not configured</option>
              <option value="uncertain">Handoff when uncertain</option>
              <option value="requested">Handoff when requested</option>
              <option value="sensitive">Handoff for sensitive actions</option>
            </Select>
          </FormField>
        </fieldset>
        <p className="text-muted-foreground mt-5 text-xs">
          Communication behavior is not connected to an agent runtime.
        </p>
      </CardContent>
    </Card>
  );
}
