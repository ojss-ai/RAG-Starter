"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { clearToken, getToken, setToken } from "@/lib/token";

export interface AuthUser {
  id: number;
  email: string;
  role: "admin" | "user";
}

interface LoginResponse {
  access_token: string;
}

export interface UseAuth {
  user: AuthUser | undefined;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export function useAuth(): UseAuth {
  const [user, setUser] = useState<AuthUser | undefined>(undefined);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    apiFetch<AuthUser>("/api/v1/auth/me", {}, token)
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiFetch<LoginResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setToken(res.access_token);
    setUser(await apiFetch<AuthUser>("/api/v1/auth/me", {}, res.access_token));
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUser(undefined);
    window.location.href = "/login";
  }, []);

  return { user, loading, login, logout };
}
