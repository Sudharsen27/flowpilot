"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { apiGet, apiPost } from "@/lib/api/client";
import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "@/lib/auth/storage";
import type {
  AuthResponse,
  MeResponse,
  OrganizationPublic,
  UserPublic,
} from "@/types/api";

type Session = {
  user: UserPublic;
  organization: OrganizationPublic;
};

type AuthContextValue = {
  session: Session | null;
  isLoading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (input: {
    email: string;
    password: string;
    name: string;
    organizationName: string;
  }) => Promise<void>;
  signOut: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const applyAuth = useCallback(
    (auth: AuthResponse | MeResponse, token?: string) => {
      if (token) {
        setAccessToken(token);
      }
      setSession({ user: auth.user, organization: auth.organization });
    },
    [],
  );

  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      const token = getAccessToken();
      if (token) {
        try {
          const me = await apiGet<MeResponse>("/api/v1/users/me");
          if (!cancelled) {
            applyAuth(me);
          }
        } catch {
          if (!cancelled) {
            clearAccessToken();
            setSession(null);
          }
        }
      }
      if (!cancelled) {
        setIsLoading(false);
      }
    }

    void restoreSession();
    return () => {
      cancelled = true;
    };
  }, [applyAuth]);

  const signIn = useCallback(
    async (email: string, password: string) => {
      const auth = await apiPost<AuthResponse>("/api/v1/auth/login", {
        email,
        password,
      });
      applyAuth(auth, auth.access_token);
    },
    [applyAuth],
  );

  const signUp = useCallback(
    async (input: {
      email: string;
      password: string;
      name: string;
      organizationName: string;
    }) => {
      const auth = await apiPost<AuthResponse>("/api/v1/auth/register", {
        email: input.email,
        password: input.password,
        name: input.name,
        organization_name: input.organizationName,
      });
      applyAuth(auth, auth.access_token);
    },
    [applyAuth],
  );

  const signOut = useCallback(() => {
    clearAccessToken();
    setSession(null);
  }, []);

  const value = useMemo(
    () => ({ session, isLoading, signIn, signUp, signOut }),
    [session, isLoading, signIn, signUp, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
