import { PlaceholderPage } from "@/components/placeholder-page";

export default function ApprovalsPage() {
  return (
    <PlaceholderPage
      title="Approvals"
      description="Review sensitive actions before they are sent or carried out."
      emptyTitle="No approvals waiting"
      emptyDescription="When an agent wants to take a high-risk action, such as sending a customer email, it will wait here for a person to approve or reject it."
    />
  );
}
