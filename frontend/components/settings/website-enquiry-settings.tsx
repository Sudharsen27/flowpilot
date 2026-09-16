"use client";

import { useEffect, useState } from "react";

import { StatePanel } from "@/components/data-display/state-panel";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import {
  getWebsiteCaptureSettings,
  updateWebsiteCaptureSettings,
} from "@/lib/api/website-capture";
import type { MembershipRole } from "@/types/api";

type WebsiteEnquirySettingsProps = {
  slug: string;
  role: MembershipRole;
};

function captureUrl(slug: string) {
  if (typeof window === "undefined") {
    return `/capture/${slug}`;
  }
  return `${window.location.origin}/capture/${slug}`;
}

export function WebsiteEnquirySettings({ slug, role }: WebsiteEnquirySettingsProps) {
  const canManage = role === "OWNER" || role === "ADMIN";
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void getWebsiteCaptureSettings()
      .then((settings) => {
        if (cancelled) return;
        setEnabled(settings.website_capture_enabled);
        setLoadError(false);
      })
      .catch(() => {
        if (!cancelled) setLoadError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [retryKey]);

  async function setCapture(next: boolean) {
    setPending(true);
    setActionError(null);
    try {
      const result = await updateWebsiteCaptureSettings(next);
      setEnabled(result.website_capture_enabled);
      setConfirmOpen(false);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 403) {
        setActionError("Only owners and admins can change this.");
      } else {
        setActionError("Website capture could not be updated. Please try again.");
      }
    } finally {
      setPending(false);
    }
  }

  async function copyUrl() {
    const url = captureUrl(slug);
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      setActionError("The URL could not be copied.");
      return;
    }
    setCopied(true);
  }

  const url = captureUrl(slug);

  return (
    <>
      {loadError ? (
        <StatePanel
          kind="error"
          title="Website enquiries could not be loaded"
          description="Try again to retrieve website capture settings."
          action={
            <Button
              type="button"
              onClick={() => {
                setLoadError(false);
                setEnabled(null);
                setRetryKey((value) => value + 1);
              }}
            >
              Try again
            </Button>
          }
        />
      ) : enabled === null ? (
        <div role="status">
          <Skeleton className="h-56 max-w-2xl" />
          <span className="sr-only">Loading website enquiry settings</span>
        </div>
      ) : (
        <Card className="max-w-2xl" as="section">
          <CardHeader>
            <CardDescription>
              Website visitors can submit an enquiry. FlowPilot will not start
              the Sales Agent or send email automatically.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm font-medium">Status</span>
              <StatusBadge
                status={enabled ? "active" : "draft"}
                label={enabled ? "On" : "Off"}
              />
            </div>
            {enabled ? (
              <p className="text-sm">
                Enquiry form URL:{" "}
                <span className="font-mono break-all">{url}</span>
              </p>
            ) : (
              <p className="text-muted-foreground text-sm">
                Website capture is off. Enquiries cannot be submitted.
              </p>
            )}
            {!canManage ? (
              <p className="text-muted-foreground text-sm">
                Only owners and admins can change this.
              </p>
            ) : null}
            {actionError ? (
              <p className="text-danger-text text-sm" role="alert">
                {actionError}
              </p>
            ) : null}
          </CardContent>
          <CardFooter className="flex flex-wrap gap-2">
            {canManage && !enabled ? (
              <Button
                type="button"
                disabled={pending}
                onClick={() => void setCapture(true)}
              >
                {pending ? "Saving…" : "Enable website enquiries"}
              </Button>
            ) : null}
            {canManage && enabled ? (
              <Button
                type="button"
                variant="outline"
                disabled={pending}
                onClick={() => setConfirmOpen(true)}
              >
                Disable website enquiries
              </Button>
            ) : null}
            {enabled ? (
              <Button type="button" variant="outline" onClick={() => void copyUrl()}>
                {copied ? "Copied" : "Copy URL"}
              </Button>
            ) : null}
          </CardFooter>
        </Card>
      )}
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Disable website enquiries?"
        description="The hosted form will stop accepting submissions. Existing leads are not changed."
        confirmLabel="Disable"
        variant="destructive"
        confirmPending={pending}
        onConfirm={() => {
          void setCapture(false);
        }}
      />
    </>
  );
}
