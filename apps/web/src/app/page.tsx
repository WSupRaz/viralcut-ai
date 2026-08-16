"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ArrowRightIcon,
  CaptionsIcon,
  CheckIcon,
  ClapperboardIcon,
  FileVideo2Icon,
  GaugeIcon,
  LanguagesIcon,
  PlayIcon,
  ScissorsIcon,
  SparklesIcon,
  UploadCloudIcon,
  Wand2Icon,
  ZapIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/stores/auth-store";
import type { PlanLimits, PlanTier } from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const NAV_LINKS = [
  { href: "#features", label: "Features" },
  { href: "#how-it-works", label: "How it works" },
  { href: "#pricing", label: "Pricing" },
  { href: "#faq", label: "FAQ" },
];

const FEATURES = [
  {
    icon: UploadCloudIcon,
    title: "Resumable uploads, up to 5 GB",
    description:
      "Chunked multipart uploads survive a dropped connection or a page refresh — you never restart a big file from zero.",
  },
  {
    icon: ScissorsIcon,
    title: "Scene & silence detection",
    description:
      "Every clip is scanned for scene changes and dead air, so the editor knows exactly where the strong moments are.",
  },
  {
    icon: Wand2Icon,
    title: "AI edit planning",
    description:
      "Claude reads the transcript and timing data — never the raw pixels — and assembles a cut list built around your style.",
  },
  {
    icon: CaptionsIcon,
    title: "Frame-accurate captions",
    description:
      "Word-level captions, punch-zooms, and transitions are composited automatically and rendered in.",
  },
  {
    icon: LanguagesIcon,
    title: "Style presets",
    description:
      "Start from a preset like Hormozi-style captions, or describe your own creative direction in plain English.",
  },
  {
    icon: ZapIcon,
    title: "Fast, hands-off export",
    description:
      "Track render progress live and download a ready-to-post vertical short the moment it's done.",
  },
];

const STEPS = [
  {
    num: "01",
    title: "Upload",
    body: "Drop in raw clips — mp4, mov, or m4v, up to 5 GB each. No trimming or prep required.",
  },
  {
    num: "02",
    title: "Analyze",
    body: "Speech-to-text, scene changes, and silence windows are extracted automatically.",
  },
  {
    num: "03",
    title: "Plan",
    body: "The AI picks the strongest moments and assembles them around your chosen style.",
  },
  {
    num: "04",
    title: "Export",
    body: "Captions and motion graphics are composited in, ready to download and post.",
  },
];

const DEFAULT_PLANS: { tier: PlanTier; name: string; price: string; tagline: string; features: string[]; cta: string }[] = [
  {
    tier: "free",
    name: "Free",
    price: "$0",
    tagline: "Try the full pipeline, no card required.",
    features: ["2 projects", "4 clips per project", "1 GB per upload", "720p exports"],
    cta: "Start free",
  },
  {
    tier: "creator",
    name: "Creator",
    price: "$19",
    tagline: "For creators shipping every week.",
    features: ["10 projects", "10 clips per project", "2 GB per upload", "1080p exports"],
    cta: "Choose Creator",
  },
  {
    tier: "pro",
    name: "Pro",
    price: "$49",
    tagline: "Serious output, minimum friction.",
    features: ["50 projects", "30 clips per project", "5 GB per upload", "4K exports"],
    cta: "Choose Pro",
  },
  {
    tier: "business",
    name: "Business",
    price: "Custom",
    tagline: "Teams and agencies at volume.",
    features: ["500 projects", "200 clips per project", "5 GB per upload", "4K exports"],
    cta: "Contact us",
  },
];

const FAQS = [
  {
    q: "Do I need any video editing experience?",
    a: "No. Upload raw footage, pick a style, and the pipeline handles the rest — detection, editing decisions, captions, and export. If you want more control you can steer the edit with instructions.",
  },
  {
    q: "What formats and sizes do you accept?",
    a: "MP4, MOV, and M4V, up to 5 GB per file. Uploads are chunked and resumable, so a bad connection won't force a restart.",
  },
  {
    q: "How is my footage used?",
    a: "Your clips are stored privately in your own project and only processed to produce your edit. The AI edit plan works from transcripts and timing data — raw frames are never sent to the language model.",
  },
  {
    q: "Can I change my plan later?",
    a: "Yes — upgrade or downgrade at any time from your account. Billing is prorated and you keep all of your projects.",
  },
  {
    q: "What happens when I hit a plan limit?",
    a: "The app stops you before you hit the wall and shows exactly what's used and what upgrading unlocks. Nothing is deleted when a plan runs out — you just need room (or a higher tier) to create more.",
  },
];

export default function Home() {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const [plans, setPlans] = useState(DEFAULT_PLANS);

  useEffect(() => {
    if (token) router.replace("/dashboard/projects");
  }, [token, router]);

  // Live plan data from the API; fall back to the static copy above if the
  // API is unreachable (e.g. first render on the marketing page).
  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/v1/plans`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled || !data?.plans) return;
        const byTier = new Map<string, PlanLimits>(
          data.plans.map((p: { tier: string; limits: PlanLimits }) => [p.tier, p.limits])
        );
        setPlans((prev) =>
          prev.map((p) => {
            const limits = byTier.get(p.tier);
            if (!limits) return p;
            const f = (b: number) => (b >= 1024 ** 3 ? `${b / 1024 ** 3} GB` : `${b / 1024 ** 2} MB`);
            return {
              ...p,
              features: [
                `${limits.max_projects} projects`,
                `${limits.max_clips_per_project} clips per project`,
                `${f(limits.max_upload_bytes)} per upload`,
                `${limits.export_qualities.join(" / ").toUpperCase()} exports`,
              ],
            };
          })
        );
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (token) return null;

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      {/* ---------- Nav ---------- */}
      <header className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <ClapperboardIcon className="size-4" />
            </span>
            <span className="text-[15px] font-semibold tracking-tight">ViralCut</span>
          </Link>
          <nav className="hidden items-center gap-7 text-sm text-muted-foreground md:flex">
            {NAV_LINKS.map((link) => (
              <a key={link.href} href={link.href} className="transition-colors hover:text-foreground">
                {link.label}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <Link href="/sign-in">
              <Button variant="ghost" size="sm">
                Sign in
              </Button>
            </Link>
            <Link href="/sign-up">
              <Button size="sm">Get started</Button>
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1">
        {/* ---------- Hero ---------- */}
        <section className="relative overflow-hidden">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_60%_50%_at_50%_-10%,oklch(0.45_0.14_275/0.28),transparent)]"
          />
          <div className="mx-auto max-w-6xl px-6 pt-24 pb-20 sm:pt-32 sm:pb-28">
            <div className="mx-auto max-w-3xl text-center">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card/60 px-3 py-1 text-xs font-medium text-muted-foreground">
                <SparklesIcon className="size-3.5 text-primary" />
                AI video editing, end to end
              </span>
              <h1 className="mt-6 text-balance text-4xl font-semibold tracking-tight sm:text-6xl">
                Raw footage in.{" "}
                <span className="text-primary">Captioned short</span> out.
              </h1>
              <p className="mx-auto mt-5 max-w-xl text-pretty text-lg text-muted-foreground">
                ViralCut finds the best moments in your footage, cuts them around your style, adds
                frame-accurate captions, and hands you a vertical short ready to post — no editing
                required.
              </p>
              <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <Link href="/sign-up">
                  <Button size="lg" className="h-11 px-7 text-[15px]">
                    Start free
                    <ArrowRightIcon className="size-4" />
                  </Button>
                </Link>
                <a href="#how-it-works">
                  <Button variant="outline" size="lg" className="h-11 px-7 text-[15px]">
                    See how it works
                  </Button>
                </a>
              </div>
              <p className="mt-4 text-xs text-muted-foreground">
                Free plan, no credit card. Resumable uploads up to 5 GB.
              </p>
            </div>

            {/* Product preview */}
            <div className="relative mx-auto mt-16 max-w-4xl">
              <div className="absolute -inset-x-8 -top-8 bottom-0 rounded-[2rem] bg-gradient-to-b from-primary/15 to-transparent blur-2xl" aria-hidden />
              <div className="relative overflow-hidden rounded-2xl border border-border bg-card shadow-2xl">
                {/* window chrome */}
                <div className="flex items-center gap-1.5 border-b border-border/60 px-4 py-3">
                  <span className="size-2.5 rounded-full bg-[oklch(0.7_0.13_25)]" />
                  <span className="size-2.5 rounded-full bg-[oklch(0.75_0.12_75)]" />
                  <span className="size-2.5 rounded-full bg-[oklch(0.7_0.12_145)]" />
                  <span className="ml-3 text-xs text-muted-foreground">viralcut.ai — Project · Launch podcast</span>
                </div>
                <div className="grid gap-0 sm:grid-cols-[240px_1fr]">
                  {/* sidebar */}
                  <div className="hidden flex-col gap-1 border-r border-border/60 p-3 text-sm sm:flex">
                    <div className="mb-2 px-2 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">Projects</div>
                    {["Launch podcast", "Client — B-roll", "Personal vlog"].map((name, i) => (
                      <div
                        key={name}
                        className={`flex items-center gap-2 rounded-lg px-2 py-1.5 ${
                          i === 0 ? "bg-primary/15 text-foreground" : "text-muted-foreground"
                        }`}
                      >
                        <FileVideo2Icon className="size-3.5" />
                        {name}
                      </div>
                    ))}
                  </div>
                  {/* main panel */}
                  <div className="flex flex-col gap-4 p-4 sm:p-5">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-sm font-medium">Launch podcast</div>
                        <div className="text-xs text-muted-foreground">3 clips · Style: Hormozi captions</div>
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                        <span className="rounded-full border border-border px-2.5 py-1 text-muted-foreground">720p</span>
                        <span className="rounded-full bg-primary px-2.5 py-1 text-primary-foreground">Export</span>
                      </div>
                    </div>
                    <div className="grid grid-cols-[1fr_auto] items-center gap-4 rounded-xl border border-border/60 bg-background/60 p-3">
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                          <span>Proxy transcode</span>
                          <span>100%</span>
                        </div>
                        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                          <div className="h-full w-full rounded-full bg-primary" />
                        </div>
                        <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                          <span>Edit plan</span>
                          <span>Done</span>
                        </div>
                        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                          <div className="h-full w-2/3 rounded-full bg-primary/70" />
                        </div>
                      </div>
                      <div className="relative h-24 w-14 overflow-hidden rounded-lg bg-black">
                        <div className="absolute inset-0 bg-gradient-to-b from-[oklch(0.5_0.15_275/0.4)] to-black" />
                        <div className="absolute inset-x-1.5 bottom-6 space-y-1">
                          <div className="h-1.5 w-10 rounded-full bg-white/90" />
                          <div className="h-1.5 w-7 rounded-full bg-white/60" />
                        </div>
                        <div className="absolute inset-0 flex items-center justify-center">
                          <span className="flex size-6 items-center justify-center rounded-full bg-white/90">
                            <PlayIcon className="ml-0.5 size-3 fill-black text-black" />
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-3 text-center text-xs">
                      {[
                        { label: "Hook", value: "9.1" },
                        { label: "Retention", value: "8.4" },
                        { label: "Engagement", value: "7.8" },
                      ].map((stat) => (
                        <div key={stat.label} className="rounded-lg border border-border/60 px-2 py-2">
                          <div className="text-base font-semibold">{stat.value}</div>
                          <div className="text-muted-foreground">{stat.label}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ---------- Features ---------- */}
        <section id="features" className="border-t border-border/60 bg-card/30">
          <div className="mx-auto max-w-6xl px-6 py-24">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
                Everything the edit needs, handled automatically
              </h2>
              <p className="mt-3 text-muted-foreground">
                One pipeline from raw clip to captioned, cut, and ready to publish.
              </p>
            </div>
            <div className="mt-14 grid gap-px overflow-hidden rounded-2xl border border-border bg-border sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map(({ icon: Icon, title, description }) => (
                <div key={title} className="flex flex-col gap-3 bg-card p-6">
                  <span className="flex size-9 items-center justify-center rounded-lg border border-border bg-muted/40">
                    <Icon className="size-4 text-primary" />
                  </span>
                  <h3 className="font-medium">{title}</h3>
                  <p className="text-sm leading-relaxed text-muted-foreground">{description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ---------- How it works ---------- */}
        <section id="how-it-works" className="border-t border-border/60">
          <div className="mx-auto max-w-6xl px-6 py-24">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">How it works</h2>
              <p className="mt-3 text-muted-foreground">Four steps from raw footage to a finished short.</p>
            </div>
            <div className="mt-14 grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
              {STEPS.map((step) => (
                <div key={step.num} className="relative">
                  <span className="font-mono text-sm text-primary">{step.num}</span>
                  <h3 className="mt-3 font-medium">{step.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{step.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ---------- Pricing ---------- */}
        <section id="pricing" className="border-t border-border/60 bg-card/30">
          <div className="mx-auto max-w-6xl px-6 py-24">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">Pricing</h2>
              <p className="mt-3 text-muted-foreground">
                Start free. Upgrade when you need more room — limits are enforced clearly, never silently.
              </p>
            </div>
            <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {plans.map((plan) => (
                <div
                  key={plan.tier}
                  className={`flex flex-col rounded-2xl border p-6 ${
                    plan.tier === "pro"
                      ? "border-primary/50 bg-primary/[0.06] shadow-[0_0_40px_-12px_oklch(0.62_0.19_275/0.4)]"
                      : "border-border bg-card"
                  }`}
                >
                  <div className="flex items-baseline justify-between">
                    <h3 className="font-semibold">{plan.name}</h3>
                    {plan.tier === "pro" && (
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
                  <Link href={plan.tier === "free" ? "/sign-up" : "/pricing"} className="mt-8">
                    <Button variant={plan.tier === "pro" ? "default" : "outline"} className="w-full">
                      {plan.cta}
                    </Button>
                  </Link>
                </div>
              ))}
            </div>
            <p className="mt-8 text-center text-xs text-muted-foreground">
              All plans include resumable uploads, scene &amp; silence detection, AI edit plans, and captions.
              Need more?{" "}
              <a href="/pricing" className="text-primary underline-offset-4 hover:underline">
                See full plan details
              </a>
              .
            </p>
          </div>
        </section>

        {/* ---------- FAQ ---------- */}
        <section id="faq" className="border-t border-border/60">
          <div className="mx-auto max-w-3xl px-6 py-24">
            <div className="text-center">
              <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">Frequently asked questions</h2>
            </div>
            <div className="mt-12 divide-y divide-border/60 border-y border-border/60">
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

        {/* ---------- CTA ---------- */}
        <section className="border-t border-border/60 bg-card/30">
          <div className="mx-auto max-w-6xl px-6 py-24">
            <div className="relative overflow-hidden rounded-3xl border border-border bg-gradient-to-br from-primary/15 via-card to-card px-8 py-16 text-center sm:px-16">
              <div
                aria-hidden
                className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_50%_60%_at_50%_0%,oklch(0.62_0.19_275/0.15),transparent)]"
              />
              <GaugeIcon className="mx-auto size-8 text-primary" />
              <h2 className="mx-auto mt-4 max-w-xl text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
                Your next short is already in the footage
              </h2>
              <p className="mx-auto mt-3 max-w-md text-muted-foreground">
                Create an account and turn your first clip into a captioned short in minutes.
              </p>
              <Link href="/sign-up">
                <Button size="lg" className="mt-8 h-12 px-8 text-base">
                  Start free
                  <ArrowRightIcon className="size-4" />
                </Button>
              </Link>
            </div>
          </div>
        </section>
      </main>

      {/* ---------- Footer ---------- */}
      <footer className="border-t border-border/60">
        <div className="mx-auto flex max-w-6xl flex-col gap-8 px-6 py-12 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-xs">
            <div className="flex items-center gap-2.5">
              <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                <ClapperboardIcon className="size-3.5" />
              </span>
              <span className="text-sm font-semibold tracking-tight">ViralCut</span>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">
              Automatic AI video editing. Upload, choose a style, and export a captioned short.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-10 text-sm sm:grid-cols-3">
            <div className="flex flex-col gap-2.5">
              <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Product</span>
              <a href="#features" className="text-muted-foreground transition-colors hover:text-foreground">Features</a>
              <a href="#pricing" className="text-muted-foreground transition-colors hover:text-foreground">Pricing</a>
              <Link href="/pricing" className="text-muted-foreground transition-colors hover:text-foreground">Plan details</Link>
            </div>
            <div className="flex flex-col gap-2.5">
              <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Account</span>
              <Link href="/sign-in" className="text-muted-foreground transition-colors hover:text-foreground">Sign in</Link>
              <Link href="/sign-up" className="text-muted-foreground transition-colors hover:text-foreground">Create account</Link>
            </div>
            <div className="flex flex-col gap-2.5">
              <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Legal</span>
              <Link href="/privacy" className="text-muted-foreground transition-colors hover:text-foreground">Privacy</Link>
              <Link href="/terms" className="text-muted-foreground transition-colors hover:text-foreground">Terms</Link>
            </div>
          </div>
        </div>
        <div className="border-t border-border/60">
          <div className="mx-auto max-w-6xl px-6 py-5 text-xs text-muted-foreground">
            © {new Date().getFullYear()} ViralCut AI. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
}
