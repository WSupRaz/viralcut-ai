import Link from "next/link";
import { ClapperboardIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

export const metadata = {
  title: "Terms of Service",
};

const SECTIONS = [
  {
    heading: "1. The service",
    body: "ViralCut AI ('ViralCut', 'we', 'us') provides an automated video editing service: you upload footage, we process it into a captioned, cut export. By creating an account or using the service you agree to these terms.",
  },
  {
    heading: "2. Your account",
    body: "You are responsible for maintaining the confidentiality of your credentials and for all activity under your account. You must provide accurate information when registering. We may suspend accounts that violate these terms or the law.",
  },
  {
    heading: "3. Acceptable use",
    body: "You may only upload footage you have the right to use. You may not upload content that is illegal, infringes someone else's rights (including copyright and privacy), or that is designed to harm the service or other users. We may remove content that violates this section.",
  },
  {
    heading: "4. Content ownership",
    body: "Your footage and your finished exports are yours. We claim no ownership of the content you upload. You grant us the limited rights needed to operate the service: store your files, process them, and produce the outputs you request.",
  },
  {
    heading: "5. Plans, limits, and billing",
    body: "The service offers free and paid plans. Plan limits (projects, clips, upload sizes, exports) are published on our pricing page and enforced automatically — the app shows your usage before you hit a limit. Paid plans are billed in advance on a monthly basis. You can change plans at any time; changes are prorated. Refunds are available within 14 days of a first purchase, except where processing has already consumed significant resources.",
  },
  {
    heading: "6. Availability",
    body: "We aim for high availability but the service is provided 'as is' without warranties of any kind. From time to time we may perform maintenance that briefly interrupts service. We are not liable for data loss — keep backups of your source footage.",
  },
  {
    heading: "7. Termination",
    body: "You may delete your account at any time. We may terminate or suspend access if you breach these terms. On termination you can download your exports before your data is deleted per our privacy policy.",
  },
  {
    heading: "8. Limitation of liability",
    body: "To the maximum extent permitted by law, ViralCut is not liable for indirect, incidental, or consequential damages arising from your use of the service. Our total liability for any claim is limited to the amount you paid us in the three months before the claim.",
  },
  {
    heading: "9. Changes to these terms",
    body: "We may update these terms as the service evolves. Material changes will be announced in-app or by email. Continued use of the service after changes take effect constitutes acceptance.",
  },
  {
    heading: "10. Contact",
    body: "Questions about these terms? Email hello@viralcut.ai.",
  },
];

export default function TermsPage() {
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
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Terms of Service</h1>
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
            <Link href="/privacy" className="transition-colors hover:text-foreground">Privacy</Link>
            <Link href="/pricing" className="transition-colors hover:text-foreground">Pricing</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
