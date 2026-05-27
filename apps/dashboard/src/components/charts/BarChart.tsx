"use client";

// Tiny inline-SVG bar chart. Designed for the analytics page's daily
// totals (cost, run volume) where the dataset is ~14–30 points — at that
// scale, pulling in a chart library would be more code than the chart.
//
// Supports stacked series so the run-volume panel can show
// completed/failed/other in one bar. Each `Series` is a list of values
// the same length as `labels`; values are stacked bottom-to-top in the
// order the series appear.

import type { CSSProperties } from "react";

export type BarSeries = {
  name: string;
  values: number[];
  color: string;
};

export function BarChart({
  labels,
  series,
  height = 160,
  yFormat = (v) => v.toFixed(0),
  ariaLabel,
}: {
  labels: string[];
  series: BarSeries[];
  height?: number;
  yFormat?: (v: number) => string;
  ariaLabel?: string;
}) {
  const cols = labels.length;
  if (cols === 0) {
    return <EmptyState height={height} message="No data in this window." />;
  }

  // Per-column totals are what set the y-axis scale on a stacked chart.
  const totals = labels.map((_, i) =>
    series.reduce((sum, s) => sum + (s.values[i] ?? 0), 0),
  );
  const yMax = Math.max(1, ...totals);

  // Layout. We render in unitless SVG-user-coordinate space then let the
  // SVG itself scale to its container. The intrinsic viewBox width grows
  // with the column count so each bar is a sensible width regardless.
  const colW = 24;
  const gap = 8;
  const padL = 36; // y-axis labels
  const padR = 8;
  const padT = 8;
  const padB = 28; // x-axis labels
  const plotW = cols * colW + (cols - 1) * gap;
  const plotH = height - padT - padB;
  const innerW = padL + plotW + padR;
  const totalH = height;

  // Nice tick values — three lines including zero.
  const ticks = [0, yMax / 2, yMax];

  return (
    <svg
      viewBox={`0 0 ${innerW} ${totalH}`}
      preserveAspectRatio="xMidYMid meet"
      className="w-full"
      style={{ height }}
      role="img"
      aria-label={ariaLabel}
    >
      {/* Y-axis grid + labels */}
      {ticks.map((t, i) => {
        const y = padT + plotH - (t / yMax) * plotH;
        return (
          <g key={i}>
            <line
              x1={padL}
              y1={y}
              x2={padL + plotW}
              y2={y}
              stroke="currentColor"
              strokeOpacity={0.1}
            />
            <text
              x={padL - 4}
              y={y}
              textAnchor="end"
              dominantBaseline="central"
              fontSize={10}
              fill="currentColor"
              fillOpacity={0.5}
            >
              {yFormat(t)}
            </text>
          </g>
        );
      })}

      {/* Bars (stacked) */}
      {labels.map((label, i) => {
        const x = padL + i * (colW + gap);
        let yCursor = padT + plotH; // bottom of plot, grow upward
        return (
          <g key={i}>
            {series.map((s) => {
              const v = s.values[i] ?? 0;
              if (v <= 0) return null;
              const segH = (v / yMax) * plotH;
              yCursor -= segH;
              return (
                <rect
                  key={s.name}
                  x={x}
                  y={yCursor}
                  width={colW}
                  height={segH}
                  fill={s.color}
                >
                  <title>{`${label} · ${s.name}: ${yFormat(v)}`}</title>
                </rect>
              );
            })}
            <text
              x={x + colW / 2}
              y={padT + plotH + 14}
              textAnchor="middle"
              fontSize={10}
              fill="currentColor"
              fillOpacity={0.6}
            >
              {label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// LineChart renders multiple series over a shared x-axis (positional, not
// time-scaled). Each series is plotted at evenly spaced x positions; for
// the analytics page that's fine because we feed it pre-aggregated daily
// buckets. Points each show a small dot + a hover title.
export type LineSeries = {
  name: string;
  values: (number | null)[]; // null = gap
  color: string;
};

export function LineChart({
  labels,
  series,
  height = 160,
  yFormat = (v) => v.toFixed(2),
  yMin,
  yMax,
  ariaLabel,
}: {
  labels: string[];
  series: LineSeries[];
  height?: number;
  yFormat?: (v: number) => string;
  yMin?: number;
  yMax?: number;
  ariaLabel?: string;
}) {
  const cols = labels.length;
  if (cols === 0 || series.every((s) => s.values.every((v) => v == null))) {
    return <EmptyState height={height} message="No data in this window." />;
  }

  const allValues = series.flatMap((s) =>
    s.values.filter((v): v is number => v != null),
  );
  const lo = yMin ?? Math.min(...allValues, 0);
  const hi = yMax ?? Math.max(...allValues, lo + 1);
  const range = Math.max(1e-6, hi - lo);

  const padL = 36;
  const padR = 8;
  const padT = 8;
  const padB = 28;
  const plotW = Math.max(120, cols * 32);
  const plotH = height - padT - padB;
  const innerW = padL + plotW + padR;

  const xAt = (i: number) =>
    cols === 1 ? padL + plotW / 2 : padL + (i / (cols - 1)) * plotW;
  const yAt = (v: number) => padT + plotH - ((v - lo) / range) * plotH;

  const ticks = [lo, (lo + hi) / 2, hi];

  return (
    <svg
      viewBox={`0 0 ${innerW} ${height}`}
      preserveAspectRatio="xMidYMid meet"
      className="w-full"
      style={{ height }}
      role="img"
      aria-label={ariaLabel}
    >
      {ticks.map((t, i) => (
        <g key={i}>
          <line
            x1={padL}
            y1={yAt(t)}
            x2={padL + plotW}
            y2={yAt(t)}
            stroke="currentColor"
            strokeOpacity={0.1}
          />
          <text
            x={padL - 4}
            y={yAt(t)}
            textAnchor="end"
            dominantBaseline="central"
            fontSize={10}
            fill="currentColor"
            fillOpacity={0.5}
          >
            {yFormat(t)}
          </text>
        </g>
      ))}

      {series.map((s) => {
        // Build the polyline from non-null segments so gaps render as breaks.
        const segments: string[] = [];
        let path = "";
        s.values.forEach((v, i) => {
          if (v == null) {
            if (path) segments.push(path);
            path = "";
            return;
          }
          const cmd = path ? "L" : "M";
          path += `${cmd}${xAt(i)},${yAt(v)} `;
        });
        if (path) segments.push(path);
        return (
          <g key={s.name}>
            {segments.map((d, i) => (
              <path
                key={i}
                d={d}
                fill="none"
                stroke={s.color}
                strokeWidth={2}
              />
            ))}
            {s.values.map((v, i) =>
              v == null ? null : (
                <circle key={i} cx={xAt(i)} cy={yAt(v)} r={3} fill={s.color}>
                  <title>{`${labels[i]} · ${s.name}: ${yFormat(v)}`}</title>
                </circle>
              ),
            )}
          </g>
        );
      })}

      {labels.map((label, i) => (
        <text
          key={i}
          x={xAt(i)}
          y={padT + plotH + 14}
          textAnchor="middle"
          fontSize={10}
          fill="currentColor"
          fillOpacity={0.6}
        >
          {label}
        </text>
      ))}
    </svg>
  );
}

export function ChartLegend({ items }: { items: { name: string; color: string }[] }) {
  return (
    <ul className="flex flex-wrap gap-3 text-xs">
      {items.map((it) => (
        <li key={it.name} className="flex items-center gap-1.5">
          <span
            aria-hidden
            className="inline-block h-2.5 w-2.5 rounded-sm"
            style={{ background: it.color }}
          />
          <span className="text-gray-600 dark:text-gray-400">{it.name}</span>
        </li>
      ))}
    </ul>
  );
}

function EmptyState({ height, message }: { height: number; message: string }) {
  // Local lightweight empty-state — the chart slot has a fixed pixel height
  // (set by the page) so we don't want to swap in the global EmptyState
  // panel; that one is designed for full-page placement. Same vocabulary
  // though: dashed border, muted icon over a short message.
  const style: CSSProperties = { height };
  return (
    <div
      style={style}
      className="flex flex-col items-center justify-center gap-1.5 rounded border border-dashed border-gray-200 text-center dark:border-gray-800"
    >
      <span
        aria-hidden
        className="text-base text-gray-400 dark:text-gray-500"
      >
        📊
      </span>
      <span className="text-xs text-gray-500 dark:text-gray-400">
        {message}
      </span>
    </div>
  );
}
