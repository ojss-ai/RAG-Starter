import type { ReactNode } from "react";
import { AuthGuard } from "@/components/AuthGuard";
import { Nav } from "@/components/Nav";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard adminOnly>
      <div className="flex min-h-screen flex-col">
        <Nav />
        {children}
      </div>
    </AuthGuard>
  );
}
