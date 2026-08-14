"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/stores/auth-store";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const user = useAuthStore((s) => s.user);
  const hasHydrated = useAuthStore((s) => s.hasHydrated);
  const clearAuth = useAuthStore((s) => s.clearAuth);

  useEffect(() => {
    // Only redirect once rehydration has finished -- otherwise a reload with
    // a valid persisted session would briefly see token=null and kick the
    // user to /sign-in, losing the in-flight upload context.
    if (hasHydrated && !token) router.replace("/sign-in");
  }, [hasHydrated, token, router]);

  if (!hasHydrated || !token) return null;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <Link href="/dashboard/projects" className="font-semibold">
            ViralCut AI
          </Link>
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            {user && <span>{user.email}</span>}
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                clearAuth();
                router.replace("/sign-in");
              }}
            >
              Sign out
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">{children}</main>
    </div>
  );
}
