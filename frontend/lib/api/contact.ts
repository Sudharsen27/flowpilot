import { apiPost } from "@/lib/api/client";

export const CONTACT_REASONS = [
  { value: "demo", label: "Request a demo" },
  { value: "product", label: "Ask about the product" },
  { value: "other", label: "Another enquiry" },
] as const;

export type ContactReason = (typeof CONTACT_REASONS)[number]["value"];

export type ContactSubmission = {
  name: string;
  email: string;
  company: string;
  jobTitle: string;
  reason: ContactReason | "";
  message: string;
  companyWebsite: string;
};

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateContact(values: ContactSubmission): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!values.name.trim()) errors.name = "Enter your full name.";
  else if (values.name.trim().length > 120) errors.name = "Use 120 characters or fewer.";
  if (!values.email.trim()) errors.email = "Enter your work email.";
  else if (!EMAIL_PATTERN.test(values.email.trim()) || values.email.trim().length > 254) {
    errors.email = "Enter a valid email address.";
  }
  if (!values.company.trim()) errors.company = "Enter your company name.";
  else if (values.company.trim().length > 120) errors.company = "Use 120 characters or fewer.";
  if (values.jobTitle.trim().length > 120) errors.jobTitle = "Use 120 characters or fewer.";
  if (!values.reason) errors.reason = "Choose a reason for contacting us.";
  if (!values.message.trim()) errors.message = "Enter a message.";
  else if (values.message.trim().length > 4000) {
    errors.message = "Use 4,000 characters or fewer.";
  }
  return errors;
}

export function submitContact(values: ContactSubmission) {
  return apiPost<{ accepted: boolean; confirmation_sent: boolean }>(
    "/api/v1/public/contact",
    {
      name: values.name.trim(),
      email: values.email.trim(),
      company: values.company.trim(),
      job_title: values.jobTitle.trim() || null,
      reason: values.reason,
      message: values.message.trim(),
      company_website: values.companyWebsite.trim() || null,
    },
    { token: null },
  );
}
