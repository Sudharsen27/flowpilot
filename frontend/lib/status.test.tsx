import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ActivityStatusBadge } from "@/components/activity/activity-status-badge";
import { AgentStatusBadge } from "@/components/agents/agent-status-badge";
import {
  ExecutionStatusBadge,
  ToolInvocationStatusBadge,
} from "@/components/agents/execution-status";
import { FollowUpStatusBadge } from "@/components/leads/follow-up-status-badge";
import { LeadStatusBadge } from "@/components/leads/lead-status-badge";
import { QualificationStatus } from "@/components/leads/qualification-status";
import {
  CANONICAL_STATUS_SEMANTICS,
  semanticStatus,
  statusPresentation,
} from "@/lib/status";
import type { LeadFollowUp } from "@/types/api";

describe("status mapping", () => {
  it("maps canonical codes onto one semantic language", () => {
    expect(CANONICAL_STATUS_SEMANTICS.COMPLETED).toBe("success");
    expect(CANONICAL_STATUS_SEMANTICS.SENT).toBe("success");
    expect(CANONICAL_STATUS_SEMANTICS.APPROVED).toBe("success");
    expect(CANONICAL_STATUS_SEMANTICS.ACTIVE).toBe("success");
    expect(CANONICAL_STATUS_SEMANTICS.QUALIFIED).toBe("success");
    expect(CANONICAL_STATUS_SEMANTICS.PENDING).toBe("pending");
    expect(CANONICAL_STATUS_SEMANTICS.QUEUED).toBe("pending");
    expect(CANONICAL_STATUS_SEMANTICS.RUNNING).toBe("pending");
    expect(CANONICAL_STATUS_SEMANTICS.READY).toBe("pending");
    expect(CANONICAL_STATUS_SEMANTICS.GENERATED).toBe("pending");
    expect(CANONICAL_STATUS_SEMANTICS.NEW).toBe("pending");
    expect(CANONICAL_STATUS_SEMANTICS.FAILED).toBe("failed");
    expect(CANONICAL_STATUS_SEMANTICS.PAUSED).toBe("paused");
    expect(CANONICAL_STATUS_SEMANTICS.CANCELLED).toBe("paused");
    expect(CANONICAL_STATUS_SEMANTICS.DRAFT).toBe("draft");
    expect(CANONICAL_STATUS_SEMANTICS.EDITED).toBe("draft");
    expect(CANONICAL_STATUS_SEMANTICS.NEEDS_ATTENTION).toBe("warning");
    expect(CANONICAL_STATUS_SEMANTICS.REJECTED).toBe("warning");
    expect(CANONICAL_STATUS_SEMANTICS.AWAITING_APPROVAL).toBe("warning");
    expect(CANONICAL_STATUS_SEMANTICS.WAITING_APPROVAL).toBe("warning");
    expect(CANONICAL_STATUS_SEMANTICS.OVERDUE).toBe("high");
  });

  it("normalizes hyphenated and lowercase domain codes", () => {
    expect(semanticStatus("needs-attention")).toBe("warning");
    expect(semanticStatus("ready")).toBe("pending");
    expect(statusPresentation("ACTIVE", "Active").status).toBe("success");
  });

  it("keeps domain labels on wrappers while using shared semantics", () => {
    const agent = render(<AgentStatusBadge status="active" />);
    expect(agent.getByText("Active")).toHaveAttribute("data-status", "success");
    agent.unmount();

    const lead = render(<LeadStatusBadge status="NEW" />);
    expect(lead.getByText("New")).toHaveAttribute("data-status", "pending");
    lead.unmount();

    const contacted = render(<LeadStatusBadge status="CONTACTED" />);
    expect(contacted.getByText("Contacted")).toHaveAttribute("data-status", "active");
    contacted.unmount();

    const execution = render(<ExecutionStatusBadge status="QUEUED" />);
    expect(execution.getByText("Queued")).toHaveAttribute("data-status", "pending");
    execution.unmount();

    const approval = render(
      <ToolInvocationStatusBadge status="AWAITING_APPROVAL" />,
    );
    expect(approval.getByText("Awaiting approval")).toHaveAttribute(
      "data-status",
      "warning",
    );
    approval.unmount();

    const activity = render(<ActivityStatusBadge status="completed" />);
    expect(activity.getByText("Completed")).toHaveAttribute("data-status", "success");
    activity.unmount();

    const followUp: LeadFollowUp = {
      id: "fu-1",
      lead_id: "lead-1",
      email_send_id: null,
      type: "EMAIL_FOLLOW_UP",
      status: "PENDING",
      due_at: "2026-01-01T00:00:00Z",
      notes: null,
      body_text: "Hello",
      revision: 1,
      is_overdue: true,
      completed_at: null,
      cancelled_at: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    const overdue = render(<FollowUpStatusBadge followUp={followUp} />);
    expect(overdue.getByText("Overdue")).toHaveAttribute("data-status", "high");
    overdue.unmount();

    const qualification = render(
      <QualificationStatus status="NEEDS_MORE_INFORMATION" />,
    );
    expect(qualification.getByText("Needs more information")).toHaveAttribute(
      "data-status",
      "pending",
    );
    expect(qualification.getByLabelText("AI Analysis")).toBeVisible();
  });
});
