import Link from "next/link";
import { ClapperboardIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

export const metadata = {
  title: "Privacy Policy",
};

const SECTIONS = [
  {
    heading: "What we collect",
    body: "We collect the information you give us directly: your name, email address, and password (stored as a salted hash, never in plain text). When you upload footage, we store the video files and the metadata derived from them (transcripts, scene timings, silence windows) so we can produce your edit. We also collect basic usage and error logs to keep the service running.",
  },
  {
    heading: "How your footage is processed",
    body: "Your clips are stored in private, per-account storage and processed only to produce your edits. The AI edit plan is generated from transcripts and timing data — raw video frames are never sent to the language model. We do not use your footage to train models, and we do not share it with third parties except the infrastructure providers that host it (cloud storage, compute, and AI APIs), all of which are bound by their own data-processing terms.",
  },
  {
    heading: "How we use your information",
    body: "We use your information to operate the service: authenticate you, process your uploads and edits, provide support, and communicate service updates. We may send occasional product emails; you can opt out at any time.",
  },
  {
    heading: "Retention & deletion",
    body: "You can delete any clip or project at any time and it is removed from our storage. If you delete your account, we delete your account data and clips within 30 days. We retain billing and legal records only as long as required by law.",
  },
  {
    heading: "Cookies & analytics",
    body: "We use a minimal set of cookies and similar technologies to keep you signed in and to understand aggregate usage of the site. We do not sell your personal data.",
  },
  {
    heading: "Your rights",
    body: "Depending on where you live (including under the GDPR and CCPA), you may have the right to access, correct, export, or delete your personal data. To exercise any of these rights, contact us at the address below and we will respond within 30 days.",
  },
  {
    heading: "Contact",
    body: "Questions about this policy or your data? Email hello@viralcut.ai and we'll get back to you.",
  },
];

export default function PrivacyPage() {
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

      <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-16">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Privacy Policy</h1>
        <p className="mt-2 text-sm text-muted-foreground">Last updated: {new Date().toLocaleDateString("en-US", { month: "long", year: "numeric" })}</p>
        <div className="mt-10 flex flex-col gap-8">
          {SECTIONS.map((section) => (
            <section key={section.heading}>
              <h2 className="text-lg font-semibold">{section.heading}</h2>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{section.body}</p>
            </section>
          ))}
        </div>
      </main>

      <footer className="border-t border-border/60">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <span>© {new Date().getFullYear()} ViralCut AI. All rights reserved.</span>
          <div className="flex items-center gap-4">
            <Link href="/terms" className="transition-colors hover:text-foreground">Terms</Link>
            <Link href="/pricing" className="transition-colors hover:text-foreground">Pricing</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
