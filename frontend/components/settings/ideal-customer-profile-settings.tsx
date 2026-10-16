"use client";

import { useEffect, useState, type FormEvent } from "react";

import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Textarea } from "@/components/forms/textarea";
import { StatePanel } from "@/components/data-display/state-panel";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import {
  getIdealCustomerProfile,
  updateIdealCustomerProfile,
} from "@/lib/api/ideal-customer-profile";
import type {
  IdealCustomerProfile,
  IdealCustomerProfileUpdate,
  MembershipRole,
} from "@/types/api";

type IdealCustomerProfileSettingsProps = {
  role: MembershipRole;
};

function termsText(terms: string[]) {
  return terms.join("\n");
}

function parseTerms(value: string) {
  return value
    .split(/\r?\n/)
    .map((term) => term.trim())
    .filter(Boolean);
}

function formPayload(
  companyTerms: string,
  companyWeight: string,
  enquiryTerms: string,
  enquiryWeight: string,
): IdealCustomerProfileUpdate | null {
  const company = parseTerms(companyTerms);
  const enquiry = parseTerms(enquiryTerms);
  const companyWeightNumber = Number(companyWeight);
  const enquiryWeightNumber = Number(enquiryWeight);
  if (
    company.length > 20 ||
    enquiry.length > 20 ||
    [...company, ...enquiry].some((term) => term.length > 120) ||
    !Number.isInteger(companyWeightNumber) ||
    !Number.isInteger(enquiryWeightNumber) ||
    companyWeightNumber < 0 ||
    companyWeightNumber > 100 ||
    enquiryWeightNumber < 0 ||
    enquiryWeightNumber > 100 ||
    (company.length > 0 && companyWeightNumber === 0) ||
    (enquiry.length > 0 && enquiryWeightNumber === 0)
  ) {
    return null;
  }
  return {
    company: { terms: company, weight: companyWeightNumber },
    enquiry: { terms: enquiry, weight: enquiryWeightNumber },
  };
}

function profileForm(profile: IdealCustomerProfile) {
  return {
    companyTerms: termsText(profile.company.terms),
    companyWeight: String(profile.company.weight),
    enquiryTerms: termsText(profile.enquiry.terms),
    enquiryWeight: String(profile.enquiry.weight),
  };
}

const unavailableLabels: Record<string, string> = {
  industry: "Industry",
  employee_range: "Company size",
  geographic_region: "Region",
  buyer_role: "Buyer role",
};

export function IdealCustomerProfileSettings({
  role,
}: IdealCustomerProfileSettingsProps) {
  const canManage = role === "OWNER" || role === "ADMIN";
  const [profile, setProfile] = useState<IdealCustomerProfile | null>(null);
  const [companyTerms, setCompanyTerms] = useState("");
  const [companyWeight, setCompanyWeight] = useState("50");
  const [enquiryTerms, setEnquiryTerms] = useState("");
  const [enquiryWeight, setEnquiryWeight] = useState("50");
  const [loadError, setLoadError] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void getIdealCustomerProfile()
      .then((result) => {
        if (cancelled) return;
        setProfile(result);
        const values = profileForm(result);
        setCompanyTerms(values.companyTerms);
        setCompanyWeight(values.companyWeight);
        setEnquiryTerms(values.enquiryTerms);
        setEnquiryWeight(values.enquiryWeight);
        setLoadError(false);
      })
      .catch(() => {
        if (!cancelled) setLoadError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [retryKey]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload = formPayload(
      companyTerms,
      companyWeight,
      enquiryTerms,
      enquiryWeight,
    );
    if (!payload) {
      setFeedback(
        "Use up to 20 terms per field, 120 characters per term, and a whole-number weight from 0 to 100. Configured criteria need a positive weight.",
      );
      return;
    }
    setPending(true);
    setFeedback(null);
    try {
      const updated = await updateIdealCustomerProfile(payload);
      setProfile(updated);
      const values = profileForm(updated);
      setCompanyTerms(values.companyTerms);
      setCompanyWeight(values.companyWeight);
      setEnquiryTerms(values.enquiryTerms);
      setEnquiryWeight(values.enquiryWeight);
      setFeedback("Profile saved.");
    } catch (cause) {
      setFeedback(
        cause instanceof ApiError && cause.status === 403
          ? "Only owners and admins can change this profile."
          : cause instanceof ApiError && cause.status === 422
            ? "The profile values are invalid. Review the terms and weights."
            : "The profile could not be saved. Try again.",
      );
    } finally {
      setPending(false);
    }
  }

  if (loadError) {
    return (
      <StatePanel
        kind="error"
        title="Prospect fit settings could not be loaded"
        description="Try again to retrieve the current organization's profile."
        action={
          <Button
            type="button"
            onClick={() => {
              setLoadError(false);
              setRetryKey((value) => value + 1);
            }}
          >
            Try again
          </Button>
        }
      />
    );
  }

  if (profile === null) {
    return (
      <div role="status">
        <Skeleton className="h-72 max-w-3xl" />
        <span className="sr-only">Loading prospect fit settings</span>
      </div>
    );
  }

  return (
    <Card as="section" className="max-w-3xl">
      <CardHeader>
        <p className="text-muted-foreground text-sm">
          Match terms in the company name and business enquiry. Weights are
          relative and do not need to total 100. Industry, company size, region,
          and buyer role are unavailable in current lead records.
        </p>
      </CardHeader>
      <form onSubmit={save}>
        <CardContent className="grid gap-5">
          {!profile.configuration_valid ? (
            <p className="text-danger-text text-sm" role="alert">
              The saved profile is invalid. Save a corrected profile to restore
              prospect scoring.
            </p>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_8rem]">
            <FormField htmlFor="icp-company-terms" label="Company match terms">
              <Textarea
                id="icp-company-terms"
                value={companyTerms}
                onChange={(event) => setCompanyTerms(event.target.value)}
                disabled={!canManage || pending}
                rows={4}
                placeholder="Acme Inc\nNorthstar"
              />
            </FormField>
            <FormField htmlFor="icp-company-weight" label="Weight">
              <Input
                id="icp-company-weight"
                type="number"
                min={0}
                max={100}
                step={1}
                value={companyWeight}
                onChange={(event) => setCompanyWeight(event.target.value)}
                disabled={!canManage || pending}
              />
            </FormField>
          </div>
          <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_8rem]">
            <FormField htmlFor="icp-enquiry-terms" label="Enquiry match terms">
              <Textarea
                id="icp-enquiry-terms"
                value={enquiryTerms}
                onChange={(event) => setEnquiryTerms(event.target.value)}
                disabled={!canManage || pending}
                rows={4}
                placeholder="analytics\nproduct demo"
              />
            </FormField>
            <FormField htmlFor="icp-enquiry-weight" label="Weight">
              <Input
                id="icp-enquiry-weight"
                type="number"
                min={0}
                max={100}
                step={1}
                value={enquiryWeight}
                onChange={(event) => setEnquiryWeight(event.target.value)}
                disabled={!canManage || pending}
              />
            </FormField>
          </div>
          <div className="text-muted-foreground text-sm" aria-live="polite">
            {feedback}
          </div>
          {Object.keys(profile.unavailable_criteria).length > 0 ? (
            <p className="text-muted-foreground text-xs">
              Not configurable:{" "}
              {Object.keys(profile.unavailable_criteria)
                .map((criterion) => unavailableLabels[criterion] ?? criterion)
                .join(", ")}
              .
            </p>
          ) : null}
          {!canManage ? (
            <p className="text-muted-foreground text-sm">
              Only owners and admins can change this profile.
            </p>
          ) : null}
        </CardContent>
        {canManage ? (
          <CardFooter>
            <Button type="submit" disabled={pending}>
              {pending ? "Saving…" : "Save profile"}
            </Button>
          </CardFooter>
        ) : null}
      </form>
    </Card>
  );
}
