import type { ReactNode } from "react";
import { AuthGuard } from "@/components/AuthGuard";
import { Nav } from "@/components/Nav";

export default function ChatLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <div className="flex h-screen flex-col">
        <Nav />
        {children}
      </div>
    </AuthGuard>
  );
}
