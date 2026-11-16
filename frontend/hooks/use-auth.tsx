"use client";

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { logoutSession } from "@/lib/api/auth";
import { apiGet, apiPost } from "@/lib/api/client";
import {
  AUTH_SESSION_INVALIDATED_EVENT,
  invalidateAuthSession,
} from "@/lib/auth/storage";
import type {
  AuthResponse,
  MembershipPublic,
  MeResponse,
  OrganizationPublic,
  UserPublic,
} from "@/types/api";

export type Session = {
  user: UserPublic;
  organization: OrganizationPublic;
  membership: MembershipPublic;
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
  completeAuth: (auth: AuthResponse) => void;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const signingOut = useRef(false);

  const applyAuth = useCallback((auth: AuthResponse | MeResponse) => {
    setSession({
      user: auth.user,
      organization: auth.organization,
      membership: auth.membership,
    });
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      try {
        const me = await apiGet<MeResponse>("/api/v1/users/me");
        if (!cancelled && me?.user && me.organization && me.membership) {
          applyAuth(me);
        } else if (!cancelled) {
          setSession(null);
        }
      } catch {
        if (!cancelled) {
          setSession(null);
        }
      }
      if (!cancelled) {
        setIsLoading(false);
      }
    }

    void restoreSession();

    function invalidateSession() {
      setSession(null);
      setIsLoading(false);
    }

    window.addEventListener(AUTH_SESSION_INVALIDATED_EVENT, invalidateSession);
    return () => {
      cancelled = true;
      window.removeEventListener(
        AUTH_SESSION_INVALIDATED_EVENT,
        invalidateSession,
      );
    };
  }, [applyAuth]);

  const signIn = useCallback(
    async (email: string, password: string) => {
      const auth = await apiPost<AuthResponse>("/api/v1/auth/login", {
        email,
        password,
      });
      applyAuth(auth);
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
      applyAuth(auth);
    },
    [applyAuth],
  );

  const completeAuth = useCallback(
    (auth: AuthResponse) => {
      applyAuth(auth);
    },
    [applyAuth],
  );

  const signOut = useCallback(async () => {
    if (signingOut.current) {
      return;
    }
    signingOut.current = true;
    try {
      await logoutSession();
    } catch {
      // Local sign-out still completes when logout is unreachable or rejected.
    } finally {
      setSession(null);
      invalidateAuthSession();
      router.replace("/login");
      router.refresh();
      signingOut.current = false;
    }
  }, [router]);

  const value = useMemo(
    () => ({ session, isLoading, signIn, signUp, completeAuth, signOut }),
    [session, isLoading, signIn, signUp, completeAuth, signOut],
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
