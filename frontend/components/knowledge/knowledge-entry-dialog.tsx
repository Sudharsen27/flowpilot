"use client";

import { type FormEvent, useState } from "react";

import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Select } from "@/components/forms/select";
import { Switch } from "@/components/forms/switch";
import { Textarea } from "@/components/forms/textarea";
import {
  KNOWLEDGE_CONTENT_MAX,
  KNOWLEDGE_TITLE_MAX,
  knowledgeCategoryHints,
  knowledgeCategoryLabels,
} from "@/components/knowledge/knowledge-labels";
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
import { ApiError } from "@/lib/api/client";
import {
  createKnowledgeEntry,
  updateKnowledgeEntry,
} from "@/lib/api/knowledge";
import type { KnowledgeCategory, KnowledgeEntry } from "@/types/api";

type KnowledgeEntryDialogProps = {
  open: boolean;
  entry?: KnowledgeEntry | null;
  onOpenChange: (open: boolean) => void;
  onSaved: (entry: KnowledgeEntry) => void;
};

function errorMessage(cause: unknown) {
  if (cause instanceof ApiError) {
    if (cause.status === 409) {
      return "Someone else changed this entry. Close this dialog, reload, and try again.";
    }
    if (cause.status === 403) {
      return "Only owners and admins can change knowledge.";
    }
    if (cause.status === 422) {
      return "Check the title and content. Both are required.";
    }
  }
  return "The entry could not be saved. Please try again.";
}

export function KnowledgeEntryDialog({
  open,
  entry,
  onOpenChange,
  onSaved,
}: KnowledgeEntryDialogProps) {
  const [category, setCategory] = useState<KnowledgeCategory>(
    entry?.category ?? "FAQ",
  );
  const [title, setTitle] = useState(entry?.title ?? "");
  const [content, setContent] = useState(entry?.content ?? "");
  const [useInAi, setUseInAi] = useState(entry?.use_in_ai ?? true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const valid = title.trim().length > 0 && content.trim().length > 0;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || !valid) return;
    setPending(true);
    setError(null);
    const input = {
      category,
      title: title.trim(),
      content: content.trim(),
      use_in_ai: useInAi,
    };
    try {
      const saved = entry
        ? await updateKnowledgeEntry(entry.id, {
            ...input,
            expected_revision: entry.revision,
          })
        : await createKnowledgeEntry(input);
      onSaved(saved);
      onOpenChange(false);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {entry ? "Edit knowledge entry" : "Add knowledge entry"}
          </DialogTitle>
          <DialogDescription>
            Write facts in plain language, the way you would tell a new
            teammate. The AI uses matching entries when it drafts replies. A
            person still approves every reply before it is sent.
          </DialogDescription>
        </DialogHeader>
        <form className="mt-6 grid gap-4" onSubmit={handleSubmit}>
          <FormField
            label="Category"
            htmlFor="knowledge-category"
            description={knowledgeCategoryHints[category]}
            required
          >
            <Select
              id="knowledge-category"
              value={category}
              onChange={(event) =>
                setCategory(event.target.value as KnowledgeCategory)
              }
            >
              {Object.entries(knowledgeCategoryLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField
            label="Title"
            htmlFor="knowledge-title"
            description="For an FAQ, write the customer's question."
            required
          >
            <Input
              id="knowledge-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={KNOWLEDGE_TITLE_MAX}
              autoFocus
              required
            />
          </FormField>
          <FormField
            label="Content"
            htmlFor="knowledge-content"
            description={`${content.length.toLocaleString()} / ${KNOWLEDGE_CONTENT_MAX.toLocaleString()} characters`}
            required
          >
            <Textarea
              id="knowledge-content"
              className="min-h-40"
              value={content}
              onChange={(event) => setContent(event.target.value)}
              maxLength={KNOWLEDGE_CONTENT_MAX}
              required
            />
          </FormField>
          <div className="border-border flex items-start justify-between gap-4 rounded-md border p-3">
            <div className="grid gap-0.5">
              <label
                htmlFor="knowledge-use-in-ai"
                className="text-sm font-medium"
              >
                Use in AI replies
              </label>
              <p
                id="knowledge-use-in-ai-help"
                className="text-muted-foreground text-xs"
              >
                Turn off for internal notes the AI should never quote to
                customers.
              </p>
            </div>
            <Switch
              id="knowledge-use-in-ai"
              checked={useInAi}
              onCheckedChange={setUseInAi}
              aria-describedby="knowledge-use-in-ai-help"
            />
          </div>
          {error ? (
            <p className="text-danger-text text-sm" role="alert">
              {error}
            </p>
          ) : null}
          <DialogFooter>
            <DialogCancel>Cancel</DialogCancel>
            <Button type="submit" disabled={pending || !valid}>
              {pending ? "Saving…" : entry ? "Save changes" : "Add entry"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
