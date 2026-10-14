"use client";

import { FormEvent, useRef, useState } from "react";

import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Textarea } from "@/components/forms/textarea";
import { ApiError } from "@/lib/api/client";
import {
  CONTACT_REASONS,
  submitContact,
  validateContact,
  type ContactReason,
  type ContactSubmission,
} from "@/lib/api/contact";

const emptyForm: ContactSubmission = {
  name: "",
  email: "",
  company: "",
  jobTitle: "",
  reason: "",
  message: "",
  companyWebsite: "",
};

function submissionError(cause: unknown): string {
  if (cause instanceof ApiError && cause.status === 429) {
    return "Please wait a moment before sending another message.";
  }
  if (cause instanceof ApiError && (cause.status === 400 || cause.status === 422)) {
    return "Check the form and try again.";
  }
  return "We could not send your message. Please try again later.";
}

export function ContactForm() {
  const [values, setValues] = useState<ContactSubmission>(emptyForm);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [sent, setSent] = useState(false);
  const [confirmationSent, setConfirmationSent] = useState(false);
  const submitting = useRef(false);

  function update<K extends keyof ContactSubmission>(key: K, value: ContactSubmission[K]) {
    setValues((current) => ({ ...current, [key]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current) return;
    const nextErrors = validateContact(values);
    setErrors(nextErrors);
    setFormError(null);
    if (Object.keys(nextErrors).length > 0) return;

    submitting.current = true;
    setPending(true);
    try {
      const result = await submitContact(values);
      setConfirmationSent(result.confirmation_sent);
      setSent(true);
    } catch (cause) {
      setFormError(submissionError(cause));
    } finally {
      submitting.current = false;
      setPending(false);
    }
  }

  if (sent) {
    return (
      <div className="border-border bg-card rounded-2xl border p-6 sm:p-8" role="status">
        <h2 className="text-2xl font-semibold tracking-[-0.03em]">Message sent</h2>
        <p className="text-muted-foreground mt-3 text-sm leading-6">
          {confirmationSent
            ? "Thanks. A short confirmation is on its way to your email. A person on the team will reply separately. This does not create an account or send a message to your customers."
            : "Thanks. The FlowPilot team has your request and will reply by email. This does not create an account or send a message to your customers."}
        </p>
      </div>
    );
  }

  return (
    <form className="border-border bg-card grid gap-5 rounded-2xl border p-6 sm:p-8" onSubmit={handleSubmit} noValidate>
      <FormField label="Full name" htmlFor="contact-name" required error={errors.name}>
        <Input
          id="contact-name"
          name="name"
          autoComplete="name"
          value={values.name}
          aria-invalid={errors.name ? true : undefined}
          aria-describedby={errors.name ? "contact-name-error" : undefined}
          onChange={(event) => update("name", event.target.value)}
        />
      </FormField>
      <FormField label="Work email" htmlFor="contact-email" required error={errors.email}>
        <Input
          id="contact-email"
          name="email"
          type="email"
          autoComplete="email"
          value={values.email}
          aria-invalid={errors.email ? true : undefined}
          aria-describedby={errors.email ? "contact-email-error" : undefined}
          onChange={(event) => update("email", event.target.value)}
        />
      </FormField>
      <FormField label="Company name" htmlFor="contact-company" required error={errors.company}>
        <Input
          id="contact-company"
          name="company"
          autoComplete="organization"
          value={values.company}
          aria-invalid={errors.company ? true : undefined}
          aria-describedby={errors.company ? "contact-company-error" : undefined}
          onChange={(event) => update("company", event.target.value)}
        />
      </FormField>
      <FormField label="Job title" htmlFor="contact-title" error={errors.jobTitle}>
        <Input
          id="contact-title"
          name="job_title"
          autoComplete="organization-title"
          value={values.jobTitle}
          aria-invalid={errors.jobTitle ? true : undefined}
          aria-describedby={errors.jobTitle ? "contact-title-error" : undefined}
          onChange={(event) => update("jobTitle", event.target.value)}
        />
      </FormField>
      <FormField
        label="Reason for contacting us"
        htmlFor="contact-reason"
        required
        error={errors.reason}
      >
        <select
          id="contact-reason"
          name="reason"
          value={values.reason}
          aria-invalid={errors.reason ? true : undefined}
          aria-describedby={errors.reason ? "contact-reason-error" : undefined}
          className="border-input bg-background text-foreground shadow-card h-9 w-full rounded-md border px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
          onChange={(event) => update("reason", event.target.value as ContactReason | "")}
        >
          <option value="">Select a reason</option>
          {CONTACT_REASONS.map((reason) => (
            <option key={reason.value} value={reason.value}>
              {reason.label}
            </option>
          ))}
        </select>
      </FormField>
      <FormField
        label="Message"
        htmlFor="contact-message"
        required
        error={errors.message}
        description="4,000 characters maximum."
      >
        <Textarea
          id="contact-message"
          name="message"
          rows={6}
          maxLength={4000}
          value={values.message}
          aria-invalid={errors.message ? true : undefined}
          aria-describedby={errors.message ? "contact-message-error" : "contact-message-description"}
          onChange={(event) => update("message", event.target.value)}
        />
      </FormField>
      <div hidden>
        <label htmlFor="contact-company-website">Company website</label>
        <input
          id="contact-company-website"
          name="company_website"
          tabIndex={-1}
          autoComplete="off"
          value={values.companyWebsite}
          onChange={(event) => update("companyWebsite", event.target.value)}
        />
      </div>
      {formError ? (
        <p className="text-danger-text text-sm" role="alert">
          {formError}
        </p>
      ) : null}
      <button
        type="submit"
        disabled={pending}
        aria-busy={pending}
        className="bg-foreground text-background hover:bg-foreground/90 focus-visible:ring-ring inline-flex h-11 w-full items-center justify-center rounded-lg px-5 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
      >
        {pending ? "Sending…" : "Send message"}
      </button>
    </form>
  );
}
