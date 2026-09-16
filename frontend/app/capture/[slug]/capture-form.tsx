"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { StatePanel } from "@/components/data-display/state-panel";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Textarea } from "@/components/forms/textarea";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import {
  getPublicEnquiryForm,
  submitPublicEnquiry,
} from "@/lib/api/website-capture";

type FieldErrors = {
  name?: string;
  email?: string;
  enquiry?: string;
};

export function CaptureEnquiryForm() {
  const params = useParams<{ slug: string }>();
  const slug = typeof params.slug === "string" ? params.slug : "";
  const [organizationName, setOrganizationName] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");
  const [enquiry, setEnquiry] = useState("");
  const [website, setWebsite] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (!slug) {
      return;
    }
    let cancelled = false;
    void getPublicEnquiryForm(slug)
      .then((form) => {
        if (cancelled) return;
        setOrganizationName(form.organization_name);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        if (cause instanceof ApiError && cause.status === 404) {
          setUnavailable(true);
          return;
        }
        setLoadError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [slug, retryKey]);

  const formLoading = Boolean(slug) && loading;
  const formUnavailable = !slug || unavailable;

  function validate(): FieldErrors {
    const next: FieldErrors = {};
    if (!name.trim()) next.name = "Name is required.";
    if (!email.trim()) next.email = "Email is required.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      next.email = "Enter a valid email address.";
    }
    if (!enquiry.trim()) next.enquiry = "Enquiry is required.";
    return next;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const nextErrors = validate();
    setFieldErrors(nextErrors);
    setSubmitError(null);
    if (Object.keys(nextErrors).length > 0) return;
    setPending(true);
    try {
      await submitPublicEnquiry(slug, {
        name: name.trim(),
        email: email.trim(),
        company: company.trim() || null,
        enquiry: enquiry.trim(),
        website: website.trim() || null,
      });
      setSuccess(true);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 404) {
        setUnavailable(true);
      } else if (cause instanceof ApiError && cause.status === 429) {
        setSubmitError("Please wait before sending another enquiry.");
      } else if (cause instanceof ApiError && cause.status === 422) {
        setSubmitError("Review the highlighted fields and try again.");
      } else {
        setSubmitError("The enquiry could not be sent. Please try again.");
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-full max-w-lg flex-col justify-center px-6 py-16">
      <p className="text-metadata text-muted-foreground font-medium tracking-wide uppercase">
        FlowPilot
      </p>
      {formLoading ? (
        <div className="mt-8 grid gap-4" role="status">
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-20 w-full" />
          <span className="sr-only">Loading enquiry form</span>
        </div>
      ) : formUnavailable ? (
        <div className="mt-8">
          <StatePanel
            kind="unavailable"
            className="max-w-none"
            title="This enquiry form is not available."
            description="The form may be turned off, or this address may be incorrect."
          />
        </div>
      ) : loadError ? (
        <div className="mt-8">
          <StatePanel
            kind="error"
            className="max-w-none"
            title="This enquiry form could not be loaded."
            description="Check your connection and try again."
            action={
              <Button
                type="button"
                onClick={() => {
                  setLoading(true);
                  setLoadError(false);
                  setRetryKey((value) => value + 1);
                }}
              >
                Retry
              </Button>
            }
          />
        </div>
      ) : success ? (
        <div className="mt-8 grid gap-3">
          <h1 className="text-page-title font-semibold tracking-tight">Contact us</h1>
          {organizationName ? (
            <p className="text-body text-muted-foreground">{organizationName}</p>
          ) : null}
          <p className="text-body" role="status">
            Thank you. We received your enquiry.
          </p>
        </div>
      ) : (
        <>
          <h1 className="text-page-title mt-4 font-semibold tracking-tight">Contact us</h1>
          {organizationName ? (
            <p className="text-section-title mt-2 font-medium">{organizationName}</p>
          ) : null}
          <p className="text-muted-foreground mt-2 text-sm">
            Send a message. A person will review it before any email is sent.
          </p>
          <form className="mt-8 flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
            <div className="absolute -left-[10000px] h-px w-px overflow-hidden" aria-hidden="true">
              <label htmlFor="website">Website</label>
              <input
                id="website"
                name="website"
                tabIndex={-1}
                autoComplete="off"
                value={website}
                onChange={(event) => setWebsite(event.target.value)}
              />
            </div>
            <FormField label="Name" htmlFor="name" required error={fieldErrors.name}>
              <Input
                id="name"
                autoComplete="name"
                value={name}
                maxLength={200}
                disabled={pending}
                onChange={(event) => setName(event.target.value)}
                required
                aria-invalid={fieldErrors.name ? true : undefined}
              />
            </FormField>
            <FormField label="Email" htmlFor="email" required error={fieldErrors.email}>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                maxLength={320}
                disabled={pending}
                onChange={(event) => setEmail(event.target.value)}
                required
                aria-invalid={fieldErrors.email ? true : undefined}
              />
            </FormField>
            <FormField label="Company" htmlFor="company">
              <Input
                id="company"
                autoComplete="organization"
                value={company}
                maxLength={200}
                disabled={pending}
                onChange={(event) => setCompany(event.target.value)}
              />
            </FormField>
            <FormField
              label="Enquiry"
              htmlFor="enquiry"
              required
              error={fieldErrors.enquiry}
            >
              <Textarea
                id="enquiry"
                value={enquiry}
                maxLength={8000}
                disabled={pending}
                onChange={(event) => setEnquiry(event.target.value)}
                required
                aria-invalid={fieldErrors.enquiry ? true : undefined}
              />
            </FormField>
            {submitError ? (
              <p className="text-danger-text text-sm" role="alert">
                {submitError}
              </p>
            ) : null}
            <Button type="submit" disabled={pending}>
              {pending ? "Submitting…" : "Submit"}
            </Button>
          </form>
        </>
      )}
    </main>
  );
}
