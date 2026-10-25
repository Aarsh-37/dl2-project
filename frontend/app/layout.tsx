import type { Metadata } from "next";
import Link from "next/link";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "CareerPilot AI — From Resume to Offer",
  description:
    "ATS score, skill gaps, roadmap, interview prep, validated resume rewrite, and matched jobs — from one resume + JD.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <header className="no-print border-b border-slate-200">
            <nav className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
              <Link href="/" className="text-lg font-bold tracking-tight">
                CareerPilot <span className="text-blue-600">AI</span>
              </Link>
              <div className="flex items-center gap-4 text-sm">
                <Link href="/analyze" className="hover:text-blue-600">Analyze</Link>
                <Link href="/history" className="hover:text-blue-600">History</Link>
                <Link
                  href="/analyze"
                  className="rounded-md bg-blue-600 px-3 py-1.5 font-medium text-white hover:bg-blue-700"
                >
                  Analyze resume
                </Link>
              </div>
            </nav>
          </header>
          <main className="mx-auto min-h-[70vh] max-w-6xl px-4 py-8">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
