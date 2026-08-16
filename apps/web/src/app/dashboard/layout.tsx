"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ClapperboardIcon, FolderOpenIcon, LogOutIcon, SparklesIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";

const PLAN_LABEL: Record<string, string> = {
  free: "Free",
  creator: "Creator",
  pro: "Pro",
  business: "Business",
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const user = useAuthStore((s) => s.user);
  const hasHydrated = useAuthStore((s) => s.hasHydrated);
  const clearAuth = useAuthStore((s) => s.clearAuth);
  const [planLabel, setPlanLabel] = useState<string | null>(null);

  useEffect(() => {
    // Only redirect once rehydration has finished -- otherwise a reload with
    // a valid persisted session would briefly see token=null and kick the
    // user to /sign-in, losing the in-flight upload context.
    if (hasHydrated && !token) router.replace("/sign-in");
  }, [hasHydrated, token, router]);

  // Live plan label from /plans/me (falls back to the user's stored plan).
  useEffect(() => {
    if (!token) return;
    api
      .myPlan(token)
      .then((data) => setPlanLabel(data.tier))
      .catch(() => {
        if (user?.plan) setPlanLabel(user.plan);
      });
  }, [token, user?.plan]);

  if (!hasHydrated || !token) return null;

  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 flex-col border-r border-border/60 bg-sidebar md:flex">
        <div className="flex h-16 items-center gap-2.5 border-b border-border/60 px-5">
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ClapperboardIcon className="size-4" />
          </span>
          <span className="text-[15px] font-semibold tracking-tight">ViralCut</span>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          <div className="mb-2 px-3 pt-2 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
            Workspace
          </div>
          <Link
            href="/dashboard/projects"
            className="flex items-center gap-2.5 rounded-lg bg-sidebar-accent px-3 py-2 text-sm font-medium text-sidebar-accent-foreground"
          >
            <FolderOpenIcon className="size-4" />
            Projects
          </Link>
        </nav>

        <div className="border-t border-border/60 p-3">
          {planLabel && (
            <div className="mb-2 flex items-center justify-between rounded-lg border border-border/60 bg-card/50 px-3 py-2">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <SparklesIcon className="size-3.5 text-primary" />
                Plan
              </div>
              <Badge variant="outline" className="capitalize">
                {PLAN_LABEL[planLabel] ?? planLabel}
              </Badge>
            </div>
          )}
          <div className="flex items-center gap-2.5 rounded-lg px-2 py-1.5">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/20 text-xs font-semibold text-primary">
              {(user?.name ?? user?.email ?? "?").slice(0, 1).toUpperCase()}
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium">{user?.name ?? "Account"}</div>
              <div className="truncate text-xs text-muted-foreground">{user?.email}</div>
            </div>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Sign out"
              title="Sign out"
              onClick={() => {
                clearAuth();
                router.replace("/sign-in");
              }}
            >
              <LogOutIcon className="text-muted-foreground" />
            </Button>
          </div>
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="fixed inset-x-0 top-0 z-40 flex h-14 items-center justify-between border-b border-border/60 bg-background/80 px-4 backdrop-blur-xl md:hidden">
        <Link href="/dashboard/projects" className="flex items-center gap-2">
          <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ClapperboardIcon className="size-3.5" />
          </span>
          <span className="text-sm font-semibold">ViralCut</span>
        </Link>
        <div className="flex items-center gap-2">
          {planLabel && (
            <Badge variant="outline" className="capitalize">
              {PLAN_LABEL[planLabel] ?? planLabel}
            </Badge>
          )}
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

      <main className="min-w-0 flex-1 px-4 pt-20 pb-12 md:ml-60 md:px-8 md:pt-8">{children}</main>
    </div>
  );
}
