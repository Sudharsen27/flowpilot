"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Select } from "@/components/forms/select";
import { Textarea } from "@/components/forms/textarea";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogCancel,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { createAgent } from "@/lib/api/agents";
import { ApiError } from "@/lib/api/client";
import type { AgentType } from "@/types/api";

type CreateAgentDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function CreateAgentDialog({
  open,
  onOpenChange,
}: CreateAgentDialogProps) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [agentType, setAgentType] = useState<AgentType>("SALES");
  const [instructions, setInstructions] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      const agent = await createAgent({
        name: name.trim(),
        description: description.trim(),
        agent_type: agentType,
        system_instructions: instructions,
      });
      onOpenChange(false);
      router.push(`/agents/${agent.id}`);
    } catch (cause) {
      setError(
        cause instanceof ApiError && cause.status === 403
          ? "You do not have permission to create agents."
          : cause instanceof ApiError && cause.status === 422
            ? "Review the agent details and correct invalid fields."
            : "The agent could not be created. Please try again.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create agent</DialogTitle>
          <DialogDescription>
            Create a draft agent. You can refine its configuration before
            making it ready.
          </DialogDescription>
        </DialogHeader>
        <form className="mt-6 grid gap-4" onSubmit={handleSubmit}>
          <FormField label="Agent name" htmlFor="create-agent-name" required>
            <Input
              id="create-agent-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              minLength={1}
              maxLength={200}
              autoFocus
              required
            />
          </FormField>
          <FormField
            label="Agent type"
            htmlFor="create-agent-type"
            required
          >
            <Select
              id="create-agent-type"
              value={agentType}
              onChange={(event) =>
                setAgentType(event.target.value as AgentType)
              }
            >
              <option value="SALES">Sales</option>
              <option value="SUPPORT">Support</option>
              <option value="OPERATIONS">Operations</option>
              <option value="COMMUNICATION">Communication</option>
            </Select>
          </FormField>
          <FormField
            label="Description"
            htmlFor="create-agent-description"
          >
            <Textarea
              id="create-agent-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              maxLength={2000}
            />
          </FormField>
          <FormField
            label="System instructions"
            htmlFor="create-agent-instructions"
            description="Define the agent's role and operating boundaries."
          >
            <Textarea
              id="create-agent-instructions"
              value={instructions}
              onChange={(event) => setInstructions(event.target.value)}
              maxLength={8000}
              className="min-h-36 font-mono text-sm"
              aria-describedby="create-agent-instructions-description"
            />
          </FormField>
          {error ? (
            <p className="text-danger-text text-sm" role="alert">
              {error}
            </p>
          ) : null}
          <DialogFooter>
            <DialogCancel>Cancel</DialogCancel>
            <Button type="submit" disabled={pending || !name.trim()}>
              {pending ? "Creating…" : "Create draft agent"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
