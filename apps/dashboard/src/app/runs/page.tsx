"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { runClient } from "@/lib/rpc";

export default function RunsPage() {
  const list = useQuery({
    queryKey: ["runs"],
    queryFn: () => runClient.listRuns({ pageSize: 50 }),
    refetchInterval: 2000,
  });

  return (
    <main className="space-y-4">
      <h1 className="text-2xl font-semibold">Runs</h1>
      {list.isLoading && <p className="text-sm text-gray-500">Loading…</p>}
      {list.isError && <p className="text-sm text-red-600">{String(list.error)}</p>}
      {list.data?.runs?.length === 0 && (
        <p className="text-sm text-gray-500">No runs yet.</p>
      )}
      <ul className="divide-y divide-gray-200 dark:divide-gray-800">
        {list.data?.runs?.map((r) => (
          <li key={r.id} className="py-3">
            <Link
              href={`/runs/${r.id}`}
              className="flex items-center justify-between hover:opacity-80"
            >
              <div>
                <div className="font-mono text-xs">{r.id}</div>
                <div className="text-xs text-gray-500">workflow {r.workflowId.slice(0, 8)}…</div>
              </div>
              <div className="text-right text-xs">
                <RunStatusBadge status={r.status} />
                <div className="mt-1 text-gray-500">${(Number(r.totalCostUsdCents) / 100).toFixed(4)}</div>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}

function RunStatusBadge({ status }: { status: number }) {
  // Numeric mirrors of RunStatus enum from the proto.
  const label = (
    {
      1: "PENDING",
      2: "RUNNING",
      3: "COMPLETED",
      4: "FAILED",
      5: "WAITING_APPROVAL",
      6: "CANCELED",
    } as Record<number, string>
  )[status] ?? "UNSPECIFIED";
  const color =
    label === "COMPLETED"
      ? "bg-green-100 text-green-800"
      : label === "FAILED"
        ? "bg-red-100 text-red-800"
        : label === "RUNNING"
          ? "bg-blue-100 text-blue-800"
          : "bg-gray-100 text-gray-800";
  return <span className={`rounded px-2 py-0.5 text-[10px] font-semibold ${color}`}>{label}</span>;
}
