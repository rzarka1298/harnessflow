export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-6 p-8 text-center">
      <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
        HarnessFlow
      </h1>
      <p className="max-w-xl text-balance text-base text-gray-500 dark:text-gray-400">
        AI workflow orchestration, observability, CI/CD, and evaluation for AI
        agents.
      </p>
      <p className="font-mono text-sm text-gray-400 dark:text-gray-500">
        Dashboard skeleton — Week 1. Workflow, run, and eval views land in
        Week 4.
      </p>
    </main>
  );
}
