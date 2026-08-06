"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import {
  CaptionsIcon,
  ClapperboardIcon,
  PaletteIcon,
  PlayIcon,
  ScissorsIcon,
  SparklesIcon,
  UploadIcon,
  Wand2Icon,
  ZapIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useAuthStore } from "@/stores/auth-store";

const FEATURES = [
  {
    icon: UploadIcon,
    title: "Direct-to-storage upload",
    description:
      "Drop in your raw footage -- mp4, mov, or m4v. Files go straight to storage, no slow server relay in the way.",
  },
  {
    icon: ScissorsIcon,
    title: "Scene & silence detection",
    description:
      "Every clip is transcribed and scanned for scene changes and dead air, so the editor knows exactly where the good parts are.",
  },
  {
    icon: Wand2Icon,
    title: "AI edit planning",
    description:
      "Claude reads the structured transcript and timing data -- never the raw pixels -- and assembles a cut list built around your style.",
  },
  {
    icon: CaptionsIcon,
    title: "Auto captions & motion graphics",
    description:
      "Word-level captions, punch-zooms, and transitions are composited automatically and rendered frame-accurate.",
  },
  {
    icon: PaletteIcon,
    title: "Style presets",
    description:
      'Start from a preset like Hormozi-style captions, or describe your own creative direction in plain English.',
  },
  {
    icon: ZapIcon,
    title: "Fast, hands-off export",
    description:
      "Track render progress in real time and grab a ready-to-post vertical short the moment it's done.",
  },
] as const;

const STEPS = [
  {
    label: "Upload",
    title: "Upload your footage",
    description: "Send us the raw clip. No trimming or prep required.",
  },
  {
    label: "Analyze",
    title: "We transcribe & analyze it",
    description: "Speech-to-text, scene changes, and silence windows, all extracted automatically.",
  },
  {
    label: "Plan",
    title: "AI builds an edit plan",
    description: "Claude picks the strongest moments and assembles them around your chosen style.",
  },
  {
    label: "Export",
    title: "Export your short",
    description: "Captions and motion graphics are composited in, ready to download and post.",
  },
] as const;

export default function Home() {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);

  useEffect(() => {
    if (token) router.replace("/dashboard/projects");
  }, [token, router]);

  if (token) return null;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-50 border-b border-border/50 bg-background/70 backdrop-blur-lg">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <span className="text-base font-semibold tracking-tight">ViralCut AI</span>
          <nav className="flex items-center gap-2">
            <Link href="/sign-in">
              <Button variant="ghost" size="sm">
                Sign in
              </Button>
            </Link>
            <Link href="/sign-up">
              <Button
                size="sm"
                className="bg-gradient-to-r from-violet-600 to-fuchsia-500 text-white hover:opacity-90"
              >
                Get started
              </Button>
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <section className="relative overflow-hidden">
          <div
            aria-hidden
            className="pointer-events-none absolute -top-48 left-1/2 -z-10 h-[620px] w-[620px] -translate-x-1/2 rounded-full bg-gradient-to-br from-violet-500/30 via-fuchsia-500/25 to-orange-400/20 blur-3xl"
          />
          <div
            aria-hidden
            className="pointer-events-none absolute top-32 right-[-120px] -z-10 h-[360px] w-[360px] rounded-full bg-gradient-to-br from-sky-400/20 to-violet-500/20 blur-3xl"
          />

          <div className="mx-auto max-w-6xl px-6 pt-20 pb-16 sm:pt-28 sm:pb-24">
            <div className="mx-auto max-w-2xl text-center">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground">
                <SparklesIcon className="size-3.5 text-violet-500" />
                AI-powered video editing
              </span>

              <h1 className="mt-6 text-5xl font-semibold tracking-tight text-balance sm:text-6xl">
                Turn raw footage into{" "}
                <span className="bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-400 bg-clip-text text-transparent">
                  scroll-stopping shorts
                </span>
              </h1>

              <p className="mt-6 text-lg text-muted-foreground text-pretty">
                Upload your footage. ViralCut AI finds the best moments, cuts them together, adds
                captions and motion graphics, and hands you a vertical short ready to post -- no
                editing required.
              </p>

              <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <Link href="/sign-up">
                  <Button
                    size="lg"
                    className="h-12 rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-500 px-8 text-base text-white hover:opacity-90"
                  >
                    Get started free
                  </Button>
                </Link>
                <Link href="/sign-in">
                  <Button variant="outline" size="lg" className="h-12 rounded-full px-8 text-base">
                    Sign in
                  </Button>
                </Link>
              </div>
            </div>

            <div className="relative mx-auto mt-20 flex h-72 items-center justify-center">
              <div
                aria-hidden
                className="absolute h-64 w-48 rotate-6 rounded-[2rem] border border-border bg-muted shadow-xl sm:h-72 sm:w-56"
              />
              <div className="relative h-64 w-48 -rotate-3 overflow-hidden rounded-[2rem] border border-border bg-gradient-to-br from-violet-600 via-fuchsia-500 to-orange-400 shadow-2xl ring-1 ring-foreground/10 sm:h-72 sm:w-56">
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/0 to-black/30" />
                <div className="absolute inset-x-0 top-5 flex justify-center">
                  <div className="h-1.5 w-14 rounded-full bg-white/40" />
                </div>
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="flex size-12 items-center justify-center rounded-full bg-white/90 shadow-lg">
                    <PlayIcon className="ml-0.5 size-5 fill-black text-black" />
                  </div>
                </div>
                <div className="absolute inset-x-6 bottom-8 flex flex-col items-center gap-2">
                  <div className="h-2 w-28 rounded-full bg-white/85" />
                  <div className="h-2 w-16 rounded-full bg-white/60" />
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="border-t border-border/50 bg-muted/30">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <div className="mx-auto max-w-xl text-center">
              <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
                Everything the edit needs, handled automatically
              </h2>
              <p className="mt-3 text-muted-foreground">
                One pipeline, from raw clip to captioned, cut, and ready to publish.
              </p>
            </div>

            <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map(({ icon: Icon, title, description }) => (
                <Card key={title} className="p-6">
                  <div className="flex size-10 items-center justify-center rounded-lg bg-gradient-to-br from-violet-600 to-fuchsia-500">
                    <Icon className="size-5 text-white" />
                  </div>
                  <h3 className="mt-4 font-heading text-base font-medium">{title}</h3>
                  <p className="mt-1.5 text-sm text-muted-foreground">{description}</p>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="border-t border-border/50">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <div className="mx-auto max-w-xl text-center">
              <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">How it works</h2>
              <p className="mt-3 text-muted-foreground">
                Four steps, from raw footage to a finished short.
              </p>
            </div>

            <div className="mt-14 grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
              {STEPS.map((step, i) => (
                <div key={step.label} className="relative">
                  <span className="bg-gradient-to-r from-violet-600 to-fuchsia-500 bg-clip-text text-4xl font-semibold text-transparent">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <h3 className="mt-3 font-heading text-base font-medium">{step.title}</h3>
                  <p className="mt-1.5 text-sm text-muted-foreground">{step.description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="border-t border-border/50 bg-muted/30">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-violet-600 via-fuchsia-500 to-orange-400 px-8 py-16 text-center shadow-2xl sm:px-16">
              <ClapperboardIcon className="mx-auto size-10 text-white/90" />
              <h2 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                Ready to go viral?
              </h2>
              <p className="mx-auto mt-3 max-w-md text-white/85">
                Create an account and turn your first clip into a short in minutes.
              </p>
              <Link href="/sign-up">
                <Button
                  size="lg"
                  className="mt-8 h-12 rounded-full bg-white px-8 text-base text-black hover:bg-white/90"
                >
                  Get started free
                </Button>
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-border/50">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 py-8 text-sm text-muted-foreground sm:flex-row">
          <span>ViralCut AI</span>
          <div className="flex items-center gap-4">
            <Link href="/sign-in" className="hover:text-foreground">
              Sign in
            </Link>
            <Link href="/sign-up" className="hover:text-foreground">
              Get started
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
