"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Plus, Trash2 } from "lucide-react";

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

type GeographicTargetForm = {
  country: string;
  region: string;
};

type ProfileFormValues = {
  companyTerms: string;
  companyWeight: string;
  enquiryTerms: string;
  enquiryWeight: string;
  industryTerms: string;
  industryWeight: string;
  minimumEmployees: string;
  maximumEmployees: string;
  companySizeWeight: string;
  geographyTargets: GeographicTargetForm[];
  geographyWeight: string;
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

function parseWeight(value: string) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 0 && parsed <= 100 ? parsed : null;
}

function parseEmployeeBound(value: string) {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : undefined;
}

function normalizedLabel(value: string) {
  return value.trim().split(/\s+/).filter(Boolean).join(" ");
}

function formPayload(values: ProfileFormValues): IdealCustomerProfileUpdate | null {
  const company = parseTerms(values.companyTerms);
  const enquiry = parseTerms(values.enquiryTerms);
  const industry = parseTerms(values.industryTerms);
  const companyWeight = parseWeight(values.companyWeight);
  const enquiryWeight = parseWeight(values.enquiryWeight);
  const industryWeight = parseWeight(values.industryWeight);
  const companySizeWeight = parseWeight(values.companySizeWeight);
  const geographyWeight = parseWeight(values.geographyWeight);
  const minimumEmployees = parseEmployeeBound(values.minimumEmployees);
  const maximumEmployees = parseEmployeeBound(values.maximumEmployees);
  const geographyTargets: { country: string; region: string | null }[] = [];
  const seenGeographyTargets = new Set<string>();
  let invalidGeography = false;
  for (const target of values.geographyTargets) {
    const country = normalizedLabel(target.country);
    const region = normalizedLabel(target.region);
    if (!country && !region) continue;
    if (!country || country.length > 120 || region.length > 120) {
      invalidGeography = true;
      continue;
    }
    const key = `${country.toLowerCase()}|${region.toLowerCase()}`;
    if (!seenGeographyTargets.has(key)) {
      geographyTargets.push({ country, region: region || null });
      seenGeographyTargets.add(key);
    }
  }
  if (
    company.length > 20 ||
    enquiry.length > 20 ||
    industry.length > 20 ||
    [...company, ...enquiry, ...industry].some((term) => term.length > 120) ||
    companyWeight === null ||
    enquiryWeight === null ||
    industryWeight === null ||
    companySizeWeight === null ||
    geographyWeight === null ||
    minimumEmployees === undefined ||
    maximumEmployees === undefined ||
    (minimumEmployees !== null && maximumEmployees !== null && minimumEmployees > maximumEmployees) ||
    ((company.length > 0 || enquiry.length > 0 || industry.length > 0) &&
      (company.length > 0 && companyWeight === 0 ||
        enquiry.length > 0 && enquiryWeight === 0 ||
        industry.length > 0 && industryWeight === 0)) ||
    ((minimumEmployees !== null || maximumEmployees !== null) && companySizeWeight === 0) ||
    (geographyTargets.length > 0 && geographyWeight === 0) ||
    geographyTargets.length > 20 ||
    invalidGeography
  ) {
    return null;
  }
  return {
    company: { terms: company, weight: companyWeight },
    enquiry: { terms: enquiry, weight: enquiryWeight },
    industry: { terms: industry, weight: industryWeight },
    company_size: {
      minimum_employees: minimumEmployees,
      maximum_employees: maximumEmployees,
      weight: companySizeWeight,
    },
    geography: { targets: geographyTargets, weight: geographyWeight },
  };
}

function profileForm(profile: IdealCustomerProfile) {
  return {
    companyTerms: termsText(profile.company.terms),
    companyWeight: String(profile.company.weight),
    enquiryTerms: termsText(profile.enquiry.terms),
    enquiryWeight: String(profile.enquiry.weight),
    industryTerms: termsText(profile.industry.terms),
    industryWeight: String(profile.industry.weight),
    minimumEmployees:
      profile.company_size.minimum_employees === null
        ? ""
        : String(profile.company_size.minimum_employees),
    maximumEmployees:
      profile.company_size.maximum_employees === null
        ? ""
        : String(profile.company_size.maximum_employees),
    companySizeWeight: String(profile.company_size.weight),
    geographyTargets:
      profile.geography.targets.length > 0
        ? profile.geography.targets.map((target) => ({
            country: target.country,
            region: target.region ?? "",
          }))
        : [{ country: "", region: "" }],
    geographyWeight: String(profile.geography.weight),
  };
}

const unavailableLabels: Record<string, string> = {
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
  const [industryTerms, setIndustryTerms] = useState("");
  const [industryWeight, setIndustryWeight] = useState("50");
  const [minimumEmployees, setMinimumEmployees] = useState("");
  const [maximumEmployees, setMaximumEmployees] = useState("");
  const [companySizeWeight, setCompanySizeWeight] = useState("50");
  const [geographyTargets, setGeographyTargets] = useState<GeographicTargetForm[]>([
    { country: "", region: "" },
  ]);
  const [geographyWeight, setGeographyWeight] = useState("50");
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
        setIndustryTerms(values.industryTerms);
        setIndustryWeight(values.industryWeight);
        setMinimumEmployees(values.minimumEmployees);
        setMaximumEmployees(values.maximumEmployees);
        setCompanySizeWeight(values.companySizeWeight);
        setGeographyTargets(values.geographyTargets);
        setGeographyWeight(values.geographyWeight);
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
    const payload = formPayload({
      companyTerms,
      companyWeight,
      enquiryTerms,
      enquiryWeight,
      industryTerms,
      industryWeight,
      minimumEmployees,
      maximumEmployees,
      companySizeWeight,
      geographyTargets,
      geographyWeight,
    });
    if (!payload) {
      setFeedback(
        "Use up to 20 terms or locations, valid inclusive employee bounds, and whole-number weights from 0 to 100. Configured criteria need a positive weight.",
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
      setIndustryTerms(values.industryTerms);
      setIndustryWeight(values.industryWeight);
      setMinimumEmployees(values.minimumEmployees);
      setMaximumEmployees(values.maximumEmployees);
      setCompanySizeWeight(values.companySizeWeight);
      setGeographyTargets(values.geographyTargets);
      setGeographyWeight(values.geographyWeight);
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
          Company and enquiry criteria score Leads. Industry, company size, and
          geography score Company Prospects using explicitly supplied evidence.
          Weights are relative and do not need to total 100.
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
          <div className="grid gap-4 border-t pt-5 sm:grid-cols-[minmax(0,1fr)_8rem]">
            <FormField htmlFor="icp-industry-terms" label="Industry target terms">
              <Textarea
                id="icp-industry-terms"
                value={industryTerms}
                onChange={(event) => setIndustryTerms(event.target.value)}
                disabled={!canManage || pending}
                rows={3}
                placeholder="Software services\nHealthcare"
              />
            </FormField>
            <FormField htmlFor="icp-industry-weight" label="Industry weight">
              <Input
                id="icp-industry-weight"
                type="number"
                min={0}
                max={100}
                step={1}
                value={industryWeight}
                onChange={(event) => setIndustryWeight(event.target.value)}
                disabled={!canManage || pending}
              />
            </FormField>
          </div>
          <section className="grid gap-4 border-t pt-5">
            <h3 className="text-sm font-semibold">Company size</h3>
            <div className="grid gap-4 sm:grid-cols-3">
              <FormField htmlFor="icp-minimum-employees" label="Minimum employees">
                <Input
                  id="icp-minimum-employees"
                  type="number"
                  min={0}
                  step={1}
                  value={minimumEmployees}
                  onChange={(event) => setMinimumEmployees(event.target.value)}
                  disabled={!canManage || pending}
                />
              </FormField>
              <FormField htmlFor="icp-maximum-employees" label="Maximum employees">
                <Input
                  id="icp-maximum-employees"
                  type="number"
                  min={0}
                  step={1}
                  value={maximumEmployees}
                  onChange={(event) => setMaximumEmployees(event.target.value)}
                  disabled={!canManage || pending}
                />
              </FormField>
              <FormField htmlFor="icp-company-size-weight" label="Company-size weight">
                <Input
                  id="icp-company-size-weight"
                  type="number"
                  min={0}
                  max={100}
                  step={1}
                  value={companySizeWeight}
                  onChange={(event) => setCompanySizeWeight(event.target.value)}
                  disabled={!canManage || pending}
                />
              </FormField>
            </div>
          </section>
          <section className="grid gap-4 border-t pt-5">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold">Geography targets</h3>
              <FormField htmlFor="icp-geography-weight" label="Geography weight">
                <Input
                  id="icp-geography-weight"
                  type="number"
                  min={0}
                  max={100}
                  step={1}
                  value={geographyWeight}
                  onChange={(event) => setGeographyWeight(event.target.value)}
                  disabled={!canManage || pending}
                />
              </FormField>
            </div>
            {geographyTargets.map((target, index) => (
              <div
                key={`geography-${index}`}
                className="grid items-end gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_2rem]"
              >
                <FormField
                  htmlFor={`icp-country-${index}`}
                  label={`Country ${index + 1}`}
                >
                  <Input
                    id={`icp-country-${index}`}
                    maxLength={120}
                    value={target.country}
                    onChange={(event) => {
                      const country = event.target.value;
                      setGeographyTargets((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, country } : item,
                        ),
                      );
                    }}
                    disabled={!canManage || pending}
                  />
                </FormField>
                <FormField
                  htmlFor={`icp-region-${index}`}
                  label={`Region ${index + 1}`}
                >
                  <Input
                    id={`icp-region-${index}`}
                    maxLength={120}
                    value={target.region}
                    onChange={(event) => {
                      const region = event.target.value;
                      setGeographyTargets((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, region } : item,
                        ),
                      );
                    }}
                    disabled={!canManage || pending}
                  />
                </FormField>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove geographic target ${index + 1}`}
                  title="Remove geographic target"
                  disabled={!canManage || pending || geographyTargets.length === 1}
                  onClick={() =>
                    setGeographyTargets((current) =>
                      current.filter((_, itemIndex) => itemIndex !== index),
                    )
                  }
                >
                  <Trash2 aria-hidden="true" />
                </Button>
              </div>
            ))}
            <Button
              type="button"
              variant="outline"
              className="w-fit"
              disabled={!canManage || pending || geographyTargets.length >= 20}
              onClick={() =>
                setGeographyTargets((current) => [
                  ...current,
                  { country: "", region: "" },
                ])
              }
            >
              <Plus aria-hidden="true" />
              Add geographic target
            </Button>
          </section>
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
