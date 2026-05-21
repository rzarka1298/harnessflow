import Link from "next/link";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-6 text-center">
      <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">HarnessFlow</h1>
      <p className="max-w-xl text-balance text-base text-gray-500 dark:text-gray-400">
        AI workflow orchestration, observability, CI/CD, and evaluation for AI agents.
      </p>
      <div className="flex gap-3">
        <Link
          href="/workflows"
          className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-300"
        >
          Browse workflows
        </Link>
        <Link
          href="/runs"
          className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium hover:border-gray-400 dark:border-gray-700 dark:hover:border-gray-500"
        >
          View runs
        </Link>
      </div>
    </main>
  );
}
