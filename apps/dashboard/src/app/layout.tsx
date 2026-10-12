import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "HarnessFlow",
  description:
    "Turn a product brief into verified code with an observable, resumable coding harness.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <Providers>
          <header className="sticky top-0 z-20 border-b border-gray-200 bg-white/85 backdrop-blur supports-[backdrop-filter]:bg-white/70 dark:border-gray-800 dark:bg-gray-950/85 dark:supports-[backdrop-filter]:bg-gray-950/70">
            <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-3 px-6 py-4">
              <Link href="/" className="font-semibold tracking-tight">
                HarnessFlow
              </Link>
              <nav
                aria-label="Main navigation"
                className="flex flex-wrap gap-4 text-sm text-gray-600 dark:text-gray-400"
              >
                <Link
                  href="/projects"
                  className="font-semibold text-teal-700 hover:text-teal-900 dark:text-teal-300"
                >
                  Projects
                </Link>
                <Link
                  href="/workflows"
                  className="hover:text-gray-900 dark:hover:text-gray-100"
                >
                  Workflows
                </Link>
                <Link
                  href="/runs"
                  className="hover:text-gray-900 dark:hover:text-gray-100"
                >
                  Workflow runs
                </Link>
                <Link
                  href="/evals"
                  className="hover:text-gray-900 dark:hover:text-gray-100"
                >
                  Evals
                </Link>
                <Link
                  href="/analytics"
                  className="hover:text-gray-900 dark:hover:text-gray-100"
                >
                  Analytics
                </Link>
                <a
                  href={
                    process.env.NEXT_PUBLIC_JAEGER_URL ??
                    "http://localhost:16686"
                  }
                  target="_blank"
                  rel="noreferrer"
                  className="hover:text-gray-900 dark:hover:text-gray-100"
                >
                  Jaeger ↗
                </a>
              </nav>
            </div>
          </header>
          <div className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
            {children}
          </div>
        </Providers>
      </body>
    </html>
  );
}
