"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { projectClient } from "@/lib/rpc";
import {
  EmptyState,
  ErrorState,
  InlineError,
  LoadingState,
} from "@/components/StateMessage";
import { readableDate, Section } from "@/components/projects/ProjectUI";

export default function ProjectsPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [repositoryPath, setRepositoryPath] = useState("");
  const [prd, setPrd] = useState("");
  const [fileError, setFileError] = useState("");
  const projects = useInfiniteQuery({
    queryKey: ["projects"],
    initialPageParam: "",
    queryFn: ({ pageParam }) =>
      projectClient.listProjects({ pageSize: 30, pageToken: pageParam }),
    getNextPageParam: (page) => page.nextPageToken || undefined,
  });
  const create = useMutation({
    mutationFn: () =>
      projectClient.createProject({
        name: name.trim(),
        repositoryPath: repositoryPath.trim(),
        prd: prd.trim(),
      }),
    onSuccess: (response) => {
      void qc.invalidateQueries({ queryKey: ["projects"] });
      if (response.project) router.push(`/projects/${response.project.id}`);
    },
  });
  const rows = projects.data?.pages.flatMap((page) => page.projects) ?? [];

  return (
    <main className="project-space space-y-8">
      <header className="project-hero">
        <div className="project-eyebrow">
          FROM REQUIREMENTS TO WORKING SOFTWARE
        </div>
        <h1>Give your project a clear next step.</h1>
        <p>
          Bring a product brief and a local Git repository. HarnessFlow plans
          the work, writes code, and checks the result in an isolated worktree.
        </p>
        <div className="project-journey" aria-label="Project workflow">
          <span>01 · Define</span>
          <span aria-hidden>→</span>
          <span>02 · Build</span>
          <span aria-hidden>→</span>
          <span>03 · Verify</span>
          <span aria-hidden>→</span>
          <span>04 · Review</span>
        </div>
      </header>
      <div className="grid items-start gap-6 lg:grid-cols-[1.25fr_1fr]">
        <Section
          title="Start a project"
          hint="A focused brief works best. Describe the outcome and what will prove it works."
        >
          <form
            className="space-y-5"
            onSubmit={(e) => {
              e.preventDefault();
              create.mutate();
            }}
          >
            <label className="project-field">
              <span>Project name</span>
              <input
                required
                maxLength={200}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Customer feedback portal"
              />
            </label>
            <label className="project-field">
              <span>Local repository path</span>
              <input
                required
                value={repositoryPath}
                onChange={(e) => setRepositoryPath(e.target.value)}
                placeholder="/Users/you/projects/feedback-portal"
                autoComplete="off"
                spellCheck={false}
              />
              <small>
                Use an existing Git repository, or initialize an empty one with{" "}
                <code>git init /path/to/project</code>. The path is on the
                machine running HarnessFlow.
              </small>
            </label>
            <label className="project-field">
              <span>Product brief / PRD</span>
              <textarea
                required
                rows={10}
                maxLength={100000}
                value={prd}
                onChange={(e) => setPrd(e.target.value)}
                placeholder={
                  "What should we build?\n\nWho is it for?\nWhat should users be able to do?\nWhat are the acceptance criteria?\nAny constraints or existing conventions?"
                }
              />
            </label>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <label className="project-upload">
                Import Markdown or text
                <input
                  className="sr-only"
                  type="file"
                  accept=".md,.markdown,.txt,text/plain,text/markdown"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    setFileError("");
                    if (file.size > 100000) {
                      setFileError("Choose a brief smaller than 100 KB.");
                      return;
                    }
                    try {
                      setPrd(await file.text());
                    } catch {
                      setFileError(
                        "This file could not be read. Paste its text instead.",
                      );
                    }
                    e.target.value = "";
                  }}
                />
              </label>
              <span className="text-xs text-gray-500">
                {prd.length.toLocaleString()} / 100,000 characters
              </span>
            </div>
            {fileError ? <InlineError error={fileError} /> : null}
            {create.isError ? <InlineError error={create.error} /> : null}
            <button
              className="project-button"
              disabled={create.isPending}
              type="submit"
            >
              {create.isPending ? "Creating project…" : "Create project →"}
            </button>
            <p className="text-xs leading-relaxed text-gray-500">
              Next, choose run limits and start the build. Creating a project
              does not run the agent.
            </p>
          </form>
        </Section>
        <Section title="Your projects" hint="Pick up where you left off.">
          {projects.isLoading ? (
            <LoadingState label="Loading projects…" />
          ) : null}
          {projects.isError ? (
            <ErrorState
              error={projects.error}
              retry={() => void projects.refetch()}
            />
          ) : null}
          {!projects.isLoading && !projects.isError && rows.length === 0 ? (
            <EmptyState
              title="Your first project starts here."
              body="Add a brief to create a workspace for the plan, runs, and verification evidence."
            />
          ) : null}
          <ul className="divide-y divide-gray-100 dark:divide-gray-800">
            {rows.map((project) => (
              <li key={project.id}>
                <Link
                  className="project-list-item"
                  href={`/projects/${project.id}`}
                >
                  <div className="min-w-0">
                    <h3>{project.name}</h3>
                    <p className="truncate font-mono text-xs">
                      {project.repositoryPath}
                    </p>
                    <small>{readableDate(project.createdAt)}</small>
                  </div>
                  <span aria-hidden>↗</span>
                </Link>
              </li>
            ))}
          </ul>
          {projects.hasNextPage ? (
            <button
              className="project-button-secondary mt-4"
              disabled={projects.isFetchingNextPage}
              onClick={() => void projects.fetchNextPage()}
            >
              Load more projects
            </button>
          ) : null}
        </Section>
      </div>
    </main>
  );
}
