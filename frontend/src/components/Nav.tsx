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
