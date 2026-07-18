# atom-15-frontend-scaffold-auth

- Status: COMMITTED
- Phase: phase-05-clients (`docs/plans/phase-05-clients.md`, item §05.2)
- Traces: FR-14 (UI), NFR-7
- Depends on: atom-13 (API surface complete)
- Mode: normal
- Created: 2026-07-12

## Purpose

The Next.js 15 App Router frontend exists: Tailwind v4, strict TypeScript (all mandatory
compiler flags), a typed API client with JWT storage and 401-redirect, the login page, an
auth guard for protected routes, and the app shell with navigation. `npm run build` +
`tsc --noEmit` are the compile oracle; pure logic is unit-tested via `node --test`.

Skill notes applied: App Router only; `"use client"` pushed to leaves; named exports
everywhere EXCEPT Next.js route-segment files (`page.tsx`/`layout.tsx`), where Next itself
mandates default exports — that is the single documented exception. Feature code lives in
`src/features/`, shared primitives in `src/lib/`.

## Files

| Path | Action |
|---|---|
| `frontend/package.json`, `tsconfig.json`, `next.config.ts`, `postcss.config.mjs` | create |
| `frontend/.env.local.example`, `frontend/next-env.d.ts` | create |
| `frontend/app/globals.css`, `app/layout.tsx`, `app/page.tsx`, `app/login/page.tsx` | create |
| `frontend/src/lib/api.ts`, `src/lib/token.ts` | create |
| `frontend/src/features/auth/hooks/useAuth.ts` | create |
| `frontend/src/components/AuthGuard.tsx`, `src/components/Nav.tsx` | create |
| `frontend/tests/api.test.ts` | create |

## Implementation

```json file=frontend/package.json
{
  "name": "ragstarter-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "typecheck": "tsc --noEmit",
    "test": "node --import tsx --test tests/*.test.ts",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "^15.1.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4.0.0",
    "@types/node": "^22.10.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "eslint": "^9.17.0",
    "eslint-config-next": "^15.1.0",
    "tailwindcss": "^4.0.0",
    "tsx": "^4.19.0",
    "typescript": "^5.7.0"
  }
}
```

```json file=frontend/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "exactOptionalPropertyTypes": true,
    "noFallthroughCasesInSwitch": true,
    "forceConsistentCasingInFileNames": true,
    "verbatimModuleSyntax": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

```typescript file=frontend/next.config.ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {};

export default nextConfig;
```

```javascript file=frontend/postcss.config.mjs
const config = {
  plugins: { "@tailwindcss/postcss": {} },
};

export default config;
```

```text file=frontend/.env.local.example
NEXT_PUBLIC_API_URL=http://localhost:8000
```

```typescript file=frontend/next-env.d.ts
/// <reference types="next" />
/// <reference types="next/image-types/global" />
```

```css file=frontend/app/globals.css
@import "tailwindcss";

:root {
  color-scheme: light;
}
```

```typescript file=frontend/src/lib/token.ts
const KEY = "rag_token";

export function getToken(): string | undefined {
  if (typeof window === "undefined") return undefined;
  return window.localStorage.getItem(KEY) ?? undefined;
}

export function setToken(token: string): void {
  window.localStorage.setItem(KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(KEY);
}
```

```typescript file=frontend/src/lib/api.ts
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export function apiUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

export function authHeaders(token: string | undefined): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function extractDetail(body: unknown, fallback: string): string {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  token?: string,
): Promise<T> {
  const response = await fetch(`${apiUrl()}${path}`, {
    ...init,
    headers: {
      ...(init.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...authHeaders(token),
      ...(init.headers ?? {}),
    },
  });
  if (response.status === 401 && typeof window !== "undefined") {
    const { clearToken } = await import("./token");
    clearToken();
    window.location.href = "/login";
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => undefined);
    throw new ApiError(response.status, extractDetail(body, response.statusText));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
```

```typescript file=frontend/src/features/auth/hooks/useAuth.ts
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
```

```tsx file=frontend/src/components/AuthGuard.tsx
"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useAuth } from "@/features/auth/hooks/useAuth";

export function AuthGuard({
  children,
  adminOnly = false,
}: {
  children: ReactNode;
  adminOnly?: boolean;
}) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login");
    else if (adminOnly && user.role !== "admin") router.replace("/chat");
  }, [user, loading, adminOnly, router]);

  if (loading || !user || (adminOnly && user.role !== "admin")) {
    return (
      <div className="flex h-screen items-center justify-center text-slate-400">
        Loading…
      </div>
    );
  }
  return <>{children}</>;
}
```

```tsx file=frontend/src/components/Nav.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/features/auth/hooks/useAuth";

export function Nav() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const link = (href: string, label: string) => (
    <Link
      href={href}
      className={`rounded px-3 py-1.5 text-sm font-medium ${
        pathname.startsWith(href)
          ? "bg-slate-800 text-white"
          : "text-slate-300 hover:bg-slate-800/60"
      }`}
    >
      {label}
    </Link>
  );

  return (
    <header className="flex items-center gap-2 border-b border-slate-800 bg-slate-900 px-4 py-2">
      <span className="mr-4 text-sm font-bold tracking-wide text-white">
        RagStarter
      </span>
      {link("/chat", "Chat")}
      {user?.role === "admin" ? link("/admin", "Admin") : null}
      <div className="ml-auto flex items-center gap-3">
        <span className="text-xs text-slate-400">{user?.email}</span>
        <button
          onClick={logout}
          className="rounded px-2 py-1 text-xs text-slate-300 hover:bg-slate-800"
        >
          Sign out
        </button>
      </div>
    </header>
  );
}
```

```tsx file=frontend/app/layout.tsx
import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "RagStarter",
  description: "Enterprise RAG — cited answers over your documents",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-950 text-slate-100 antialiased">
        {children}
      </body>
    </html>
  );
}
```

```tsx file=frontend/app/page.tsx
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/chat");
}
```

```tsx file=frontend/app/login/page.tsx
"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/features/auth/hooks/useAuth";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | undefined>(undefined);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(undefined);
    try {
      await login(email, password);
      router.replace("/chat");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm space-y-4 rounded-xl border border-slate-800 bg-slate-900 p-8"
      >
        <h1 className="text-lg font-semibold">Sign in to RagStarter</h1>
        <label className="block text-sm">
          <span className="mb-1 block text-slate-400">Email</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 outline-none focus:border-slate-400"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-slate-400">Password</span>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 outline-none focus:border-slate-400"
          />
        </label>
        {error ? <p className="text-sm text-red-400">{error}</p> : null}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded bg-slate-100 py-2 text-sm font-semibold text-slate-900 hover:bg-white disabled:opacity-50"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
```

## Tests (normal mode: must exist before validate)

```typescript file=frontend/tests/api.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";
import { authHeaders, extractDetail } from "../src/lib/api";

test("authHeaders with and without token", () => {
  assert.deepEqual(authHeaders("abc"), { Authorization: "Bearer abc" });
  assert.deepEqual(authHeaders(undefined), {});
});

test("extractDetail reads FastAPI error shape", () => {
  assert.equal(extractDetail({ detail: "Invalid credentials" }, "x"), "Invalid credentials");
  assert.equal(extractDetail({ detail: { nested: true } }, "fallback"), "fallback");
  assert.equal(extractDetail(undefined, "fallback"), "fallback");
  assert.equal(extractDetail("weird", "fallback"), "fallback");
});
```

Notes: `npm install` then `npm run typecheck && npm test && npm run build` is the full
oracle. `apiFetch` handles FormData bodies (no forced Content-Type) — the admin upload UI
(atom-17) depends on that. 401 anywhere clears the token and bounces to `/login`.

## Verification

1. `cd frontend && npm install && npm run typecheck && npm test` → green.
2. `npm run build` → compiles clean.
3. Manual: `npm run dev` with the API up → login with bootstrap admin → redirected to /chat shell.

## Review Log

- 2026-07-17 — review-atom: freshness ✓ (auth API shape matches atoms 04/05: /auth/login TokenResponse, /auth/me role field), completeness ✓ (all config + source files with full code; nextjs/react/typescript skill rules respected — default exports only in route-segment files), traceability ✓ (FR-14 UI, NFR-7 / plan §05.2). Certified READY.

## Implementation Log

- 2026-07-17 — Implemented per atom. One deviation (atom updated): the test script
  `node --import tsx --test tests/` fails on Node 22 (directory resolved as module);
  changed to `node --import tsx --test tests/*.test.ts`. Oracle: `tsc --noEmit` clean,
  `npm test` 2/2 pass, `next build` clean (static routes /, /login).
- 2026-07-17 — VALIDATED. All three oracle legs green. Manual dev-server login flow
  deferred to atom-16/17 validation (same auth path exercised there). No OPEN findings.
  review-change clean.
