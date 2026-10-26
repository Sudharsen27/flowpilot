"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Select } from "@/components/forms/select";
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
import { createCompanyProspect } from "@/lib/api/company-prospects";
import { ApiError } from "@/lib/api/client";
import type { EvidenceQuality } from "@/types/api";

type CompanyProspectCreateDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: (prospectId: string) => void;
};

export function CompanyProspectCreateDialog({
  open,
  onOpenChange,
  onCreated,
}: CompanyProspectCreateDialogProps) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [websiteDomain, setWebsiteDomain] = useState("");
  const [nameEvidenceQuality, setNameEvidenceQuality] =
    useState<EvidenceQuality>("UNKNOWN");
  const [websiteDomainEvidenceQuality, setWebsiteDomainEvidenceQuality] =
    useState<EvidenceQuality>("UNKNOWN");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    const domainTrimmed = websiteDomain.trim();
    const domainValue = domainTrimmed ? domainTrimmed : null;
    const domainQuality = domainValue ? websiteDomainEvidenceQuality : "UNKNOWN";

    try {
      const prospect = await createCompanyProspect({
        name: name.trim(),
        website_domain: domainValue,
        name_evidence_quality: nameEvidenceQuality,
        website_domain_evidence_quality: domainQuality,
      });
      onOpenChange(false);
      setName("");
      setWebsiteDomain("");
      setNameEvidenceQuality("UNKNOWN");
      setWebsiteDomainEvidenceQuality("UNKNOWN");
      if (onCreated) {
        onCreated(prospect.id);
      } else {
        router.push(`/company-prospects/${prospect.id}`);
      }
      router.refresh();
    } catch (cause) {
      setError(
        cause instanceof ApiError && cause.status === 403
          ? "You do not have permission to create company prospects."
          : cause instanceof ApiError && cause.status === 409
            ? "A company prospect with this website domain already exists in this organization."
            : cause instanceof ApiError && cause.status === 422
              ? "Review the company details and correct invalid fields or domain formats."
              : "The company prospect could not be created. Please try again.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add company prospect</DialogTitle>
          <DialogDescription>
            Manually add a company prospect to this organization’s catalog.
          </DialogDescription>
        </DialogHeader>
        <form className="mt-6 grid gap-4" onSubmit={handleSubmit}>
          <FormField
            label="Company name"
            htmlFor="create-prospect-name"
            required
          >
            <Input
              id="create-prospect-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              minLength={1}
              maxLength={200}
              autoFocus
              required
            />
          </FormField>
          <FormField
            label="Website domain"
            htmlFor="create-prospect-domain"
            description="Optional fully qualified domain without URL path (e.g., example.com)."
          >
            <Input
              id="create-prospect-domain"
              value={websiteDomain}
              onChange={(event) => setWebsiteDomain(event.target.value)}
              maxLength={253}
              placeholder="example.com"
            />
          </FormField>
          <FormField
            label="Name evidence quality"
            htmlFor="create-prospect-name-evidence"
          >
            <Select
              id="create-prospect-name-evidence"
              value={nameEvidenceQuality}
              onChange={(event) =>
                setNameEvidenceQuality(event.target.value as EvidenceQuality)
              }
            >
              <option value="UNKNOWN">Unknown</option>
              <option value="SOURCE_REPORTED">Source Reported</option>
              <option value="ESTIMATED">Estimated</option>
              <option value="INFERRED">Inferred</option>
            </Select>
          </FormField>
          <FormField
            label="Domain evidence quality"
            htmlFor="create-prospect-domain-evidence"
            description="Must be Unknown if website domain is empty."
          >
            <Select
              id="create-prospect-domain-evidence"
              value={websiteDomain ? websiteDomainEvidenceQuality : "UNKNOWN"}
              disabled={!websiteDomain.trim()}
              onChange={(event) =>
                setWebsiteDomainEvidenceQuality(
                  event.target.value as EvidenceQuality,
                )
              }
            >
              <option value="UNKNOWN">Unknown</option>
              <option value="SOURCE_REPORTED">Source Reported</option>
              <option value="ESTIMATED">Estimated</option>
              <option value="INFERRED">Inferred</option>
            </Select>
          </FormField>
          {error ? (
            <p className="text-danger-text text-sm" role="alert">
              {error}
            </p>
          ) : null}
          <DialogFooter>
            <DialogCancel>Cancel</DialogCancel>
            <Button type="submit" disabled={pending || !name.trim()}>
              {pending ? "Adding…" : "Add company prospect"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
