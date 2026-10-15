export const DEMO_LEAD = {
  name: "Alex Morgan",
  company: "Northstar Analytics",
  role: "Operations Director",
  crmStatus: "New",
  enquiry:
    "We are evaluating a sales operations platform for a 20-person team. We need lead qualification and controlled follow-up.",
  activity: ["Website enquiry received", "Lead added to the workspace"],
} as const;

export const DEMO_QUALIFICATION = {
  intent: "Evaluating a sales operations platform",
  buyingSignals: [
    "Team size identified",
    "Qualification and follow-up needs stated",
  ],
  missingInformation: ["Budget", "Implementation timeline", "Decision process"],
  confidence: "86%",
} as const;

export const DEMO_RESPONSE = `Hi Alex,

Thank you for sharing how Northstar Analytics is evaluating sales operations for a 20-person team. FlowPilot can help your team structure incoming lead qualification and keep follow-up work visible, while people remain in control of customer communication.

Would you be open to sharing your implementation timeline and who would be involved in the decision? That will help us tailor a useful walkthrough to your team.

Best,
FlowPilot team`;
