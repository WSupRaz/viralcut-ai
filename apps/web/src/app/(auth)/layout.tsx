import Link from "next/link";
import { ClapperboardIcon } from "lucide-react";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_50%_40%_at_50%_-10%,oklch(0.45_0.14_275/0.22),transparent)]"
      />
      <div className="relative w-full max-w-sm">
        <Link href="/" className="mb-8 flex items-center justify-center gap-2.5">
          <span className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ClapperboardIcon className="size-4.5" />
          </span>
          <span className="text-lg font-semibold tracking-tight">ViralCut</span>
        </Link>
        {children}
        <p className="mt-8 text-center text-xs text-muted-foreground">
          <Link href="/privacy" className="transition-colors hover:text-foreground">Privacy</Link>
          {" · "}
          <Link href="/terms" className="transition-colors hover:text-foreground">Terms</Link>
        </p>
      </div>
    </div>
  );
}
