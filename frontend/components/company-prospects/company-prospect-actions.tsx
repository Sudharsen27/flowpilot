"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { updateCompanyProspectLifecycle } from "@/lib/api/company-prospects";
import { ApiError } from "@/lib/api/client";
import type { CompanyProspect, CompanyProspectStatus } from "@/types/api";

type CompanyProspectActionsProps = {
  prospect: CompanyProspect;
  onUpdated?: (updated: CompanyProspect) => void;
};

export function CompanyProspectActions({
  prospect,
  onUpdated,
}: CompanyProspectActionsProps) {
  const router = useRouter();
  const { session } = useAuth();
  const [pendingStatus, setPendingStatus] =
    useState<CompanyProspectStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const role = session?.membership.role;
  const isManager = role === "OWNER" || role === "ADMIN";

  async function handleTransition(targetStatus: CompanyProspectStatus) {
    if (!isManager) return;
    setError(null);
    setPendingStatus(targetStatus);
    try {
      const updated = await updateCompanyProspectLifecycle(
        prospect.id,
        targetStatus,
      );
      if (onUpdated) {
        onUpdated(updated);
      }
      router.refresh();
    } catch (cause) {
      setError(
        cause instanceof ApiError && cause.status === 403
          ? "You do not have permission to modify company prospects."
          : "Status transition failed. Please try again.",
      );
    } finally {
      setPendingStatus(null);
    }
  }

  if (!isManager) {
    return (
      <p className="text-muted-foreground text-sm">
        Management actions (review, archive, restore) require Owner or Admin
        permissions.
      </p>
    );
  }

  const currentStatus = prospect.status;

  return (
    <div className="flex flex-wrap items-center gap-3">
      {currentStatus === "IDENTIFIED" ? (
        <>
          <Button
            type="button"
            variant="outline"
            disabled={pendingStatus !== null}
            onClick={() => handleTransition("REVIEWED")}
          >
            {pendingStatus === "REVIEWED" ? "Updating…" : "Mark reviewed"}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={pendingStatus !== null}
            onClick={() => handleTransition("ARCHIVED")}
          >
            {pendingStatus === "ARCHIVED" ? "Updating…" : "Archive"}
          </Button>
        </>
      ) : null}

      {currentStatus === "REVIEWED" ? (
        <>
          <Button
            type="button"
            variant="outline"
            disabled={pendingStatus !== null}
            onClick={() => handleTransition("IDENTIFIED")}
          >
            {pendingStatus === "IDENTIFIED" ? "Updating…" : "Mark identified"}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={pendingStatus !== null}
            onClick={() => handleTransition("ARCHIVED")}
          >
            {pendingStatus === "ARCHIVED" ? "Updating…" : "Archive"}
          </Button>
        </>
      ) : null}

      {currentStatus === "ARCHIVED" ? (
        <Button
          type="button"
          variant="outline"
          disabled={pendingStatus !== null}
          onClick={() => handleTransition("IDENTIFIED")}
        >
          {pendingStatus === "IDENTIFIED" ? "Updating…" : "Restore"}
        </Button>
      ) : null}

      {error ? (
        <p className="text-danger-text text-sm" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
