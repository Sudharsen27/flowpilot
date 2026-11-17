import { expect, type APIRequestContext } from "@playwright/test";

const API_URL = process.env.E2E_API_URL ?? "http://127.0.0.1:8010";

/** Register and clear B2 for the disposable E2E API only. */
export async function registerVerifiedOwner(
  request: APIRequestContext,
  input: {
    email: string;
    password?: string;
    name?: string;
    organizationName: string;
  },
) {
  const password = input.password ?? "password12";
  const registered = await request.post(`${API_URL}/api/v1/auth/register`, {
    data: {
      email: input.email,
      password,
      name: input.name ?? "E2E Owner",
      organization_name: input.organizationName,
    },
  });
  expect(registered.ok()).toBeTruthy();
  const account = (await registered.json()) as {
    access_token: string;
    organization: { slug: string; id: string };
  };
  const verified = await request.post(`${API_URL}/api/v1/auth/e2e/mark-verified`, {
    headers: { Authorization: `Bearer ${account.access_token}` },
  });
  expect(verified.ok()).toBeTruthy();
  return { ...account, password };
}
