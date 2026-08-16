import Link from "next/link";
import { ClapperboardIcon, CheckIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

// Static snapshot of the plan limits (mirrors app/core/plan_limits.py). The
// live limits are served by the API and shown on the landing page; this page
// is static so it renders instantly on Vercel's edge. If the two drift,
// plan_limits.py is the source of truth.
const PLANS = [
  {
    tier: "free",
    name: "Free",
    price: "$0",
    tagline: "Try the full pipeline, no card required.",
    features: ["2 projects", "4 clips per project", "1 GB per upload", "720p exports", "3 exports per project"],
    cta: "Start free",
    href: "/sign-up",
    highlighted: false,
  },
  {
    tier: "creator",
    name: "Creator",
    price: "$19",
    tagline: "For creators shipping every week.",
    features: ["10 projects", "10 clips per project", "2 GB per upload", "720p + 1080p exports", "20 exports per project"],
    cta: "Choose Creator",
    href: "/sign-up",
    highlighted: false,
  },
  {
    tier: "pro",
    name: "Pro",
    price: "$49",
    tagline: "Serious output, minimum friction.",
    features: ["50 projects", "30 clips per project", "5 GB per upload", "Up to 4K exports", "100 exports per project"],
    cta: "Choose Pro",
    href: "/sign-up",
    highlighted: true,
  },
  {
    tier: "business",
    name: "Business",
    price: "Custom",
    tagline: "Teams and agencies at volume.",
    features: ["500 projects", "200 clips per project", "5 GB per upload", "Up to 4K exports", "1,000 exports per project"],
    cta: "Contact us",
    href: "mailto:hello@viralcut.ai",
    highlighted: false,
  },
];

const COMPARISON: { label: string; values: Record<string, string> }[] = [
  { label: "Projects", values: { free: "2", creator: "10", pro: "50", business: "500" } },
  { label: "Clips per project", values: { free: "4", creator: "10", pro: "30", business: "200" } },
  { label: "Max upload size", values: { free: "1 GB", creator: "2 GB", pro: "5 GB", business: "5 GB" } },
  { label: "Export quality", values: { free: "720p", creator: "1080p", pro: "4K", business: "4K" } },
  { label: "Exports per project", values: { free: "3", creator: "20", pro: "100", business: "1,000" } },
  { label: "Resumable uploads", values: { free: "✓", creator: "✓", pro: "✓", business: "✓" } },
  { label: "Scene & silence detection", values: { free: "✓", creator: "✓", pro: "✓", business: "✓" } },
  { label: "AI edit plans", values: { free: "✓", creator: "✓", pro: "✓", business: "✓" } },
  { label: "Frame-accurate captions", values: { free: "✓", creator: "✓", pro: "✓", business: "✓" } },
];

const FAQS = [
  {
    q: "Is there really a free plan?",
    a: "Yes. The Free plan gives you the full pipeline — uploads, detection, AI edit plans, captions, exports — with limits that are clearly shown in the app before you hit them. No credit card required.",
  },
  {
    q: "Can I upgrade or downgrade later?",
    a: "Yes. You can change plans at any time from your account. Your projects and clips are never deleted when you move between plans.",
  },
  {
    q: "What counts as a project or a clip?",
    a: "A project is a single video you're producing (e.g. one episode or one ad). A clip is one uploaded source video inside that project. Deleting a clip or project frees up room immediately.",
  },
  {
    q: "What happens when I hit a limit?",
    a: "The app stops you before the wall and tells you exactly what's used and what upgrading unlocks. Nothing is silently blocked or deleted.",
  },
];

export const metadata = {
  title: "Pricing",
};

export default function PricingPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <ClapperboardIcon className="size-4" />
            </span>
            <span className="text-[15px] font-semibold tracking-tight">ViralCut</span>
          </Link>
          <div className="flex items-center gap-2">
            <Link href="/sign-in">
              <Button variant="ghost" size="sm">Sign in</Button>
            </Link>
            <Link href="/sign-up">
              <Button size="sm">Get started</Button>
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <section className="mx-auto max-w-6xl px-6 pt-20 pb-24">
          <div className="mx-auto max-w-2xl text-center">
            <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">Pricing</h1>
            <p className="mt-4 text-lg text-muted-foreground">
              Start free and upgrade when you need more room. Every plan includes the full pipeline.
            </p>
          </div>

          <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {PLANS.map((plan) => (
              <div
                key={plan.tier}
                className={`flex flex-col rounded-2xl border p-6 ${
                  plan.highlighted
                    ? "border-primary/50 bg-primary/[0.06] shadow-[0_0_40px_-12px_oklch(0.62_0.19_275/0.4)]"
                    : "border-border bg-card"
                }`}
              >
                <div className="flex items-baseline justify-between">
                  <h2 className="font-semibold">{plan.name}</h2>
                  {plan.highlighted && (
                    <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[11px] font-medium text-primary">
                      Popular
                    </span>
                  )}
                </div>
                <div className="mt-4 flex items-baseline gap-1">
                  <span className="text-3xl font-semibold tracking-tight">{plan.price}</span>
                  {plan.price !== "Custom" && <span className="text-sm text-muted-foreground">/mo</span>}
                </div>
                <p className="mt-1.5 text-xs text-muted-foreground">{plan.tagline}</p>
                <ul className="mt-6 flex flex-1 flex-col gap-2.5 text-sm">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-center gap-2.5">
                      <CheckIcon className="size-4 shrink-0 text-primary" />
                      <span className="text-muted-foreground">{feature}</span>
                    </li>
                  ))}
                </ul>
                <Link href={plan.href} className="mt-8">
                  <Button variant={plan.highlighted ? "default" : "outline"} className="w-full">
                    {plan.cta}
                  </Button>
                </Link>
              </div>
            ))}
          </div>

          {/* Comparison table */}
          <div className="mt-24">
            <h2 className="text-center text-2xl font-semibold tracking-tight">Compare plans</h2>
            <div className="mx-auto mt-8 max-w-4xl overflow-x-auto rounded-2xl border border-border">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border bg-card/40">
                    <th className="px-5 py-3.5 text-left font-medium text-muted-foreground">Feature</th>
                    {PLANS.map((plan) => (
                      <th key={plan.tier} className="px-5 py-3.5 text-center font-medium capitalize">
                        {plan.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {COMPARISON.map((row, i) => (
                    <tr key={row.label} className={i % 2 ? "bg-card/20" : "bg-transparent"}>
                      <td className="px-5 py-3 text-muted-foreground">{row.label}</td>
                      {PLANS.map((plan) => (
                        <td key={plan.tier} className="px-5 py-3 text-center">
                          {row.values[plan.tier]}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* FAQ */}
          <div className="mx-auto mt-24 max-w-3xl">
            <h2 className="text-center text-2xl font-semibold tracking-tight">Questions</h2>
            <div className="mt-8 divide-y divide-border/60 border-y border-border/60">
              {FAQS.map((faq) => (
                <details key={faq.q} className="group py-5">
                  <summary className="flex cursor-pointer list-none items-center justify-between text-[15px] font-medium [&::-webkit-details-marker]:hidden">
                    {faq.q}
                    <span className="ml-4 text-muted-foreground transition-transform group-open:rotate-45">+</span>
                  </summary>
                  <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{faq.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-border/60">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <span>© {new Date().getFullYear()} ViralCut AI. All rights reserved.</span>
          <div className="flex items-center gap-4">
            <Link href="/privacy" className="transition-colors hover:text-foreground">Privacy</Link>
            <Link href="/terms" className="transition-colors hover:text-foreground">Terms</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
