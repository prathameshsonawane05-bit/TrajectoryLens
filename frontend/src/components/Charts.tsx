import { findingColor, findingLabel } from "../failureTypes";

export interface ChartRow {
  label: string;
  value: number;
  color: string;
}

interface BarChartProps {
  title: string;
  rows: ChartRow[];
}

export function BarChart({ title, rows }: BarChartProps) {
  const width = 720;
  const labelWidth = 168;
  const barHeight = 22;
  const gap = 10;
  const height = Math.max(rows.length, 1) * (barHeight + gap) + 8;
  const max = Math.max(1, ...rows.map((row) => row.value));
  const barArea = width - labelWidth - 48;

  return (
    <figure className="chart">
      <figcaption>{title}</figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title}>
        {rows.map((row, index) => {
          const y = index * (barHeight + gap);
          const barWidth = (row.value / max) * barArea;
          return (
            <g key={row.label} transform={`translate(0 ${y})`}>
              <text x={0} y={barHeight - 6} className="chart-label">
                {row.label}
              </text>
              <rect
                x={labelWidth}
                y={0}
                width={Math.max(barWidth, row.value > 0 ? 2 : 0)}
                height={barHeight}
                fill={row.color}
                rx={3}
              />
              <text x={labelWidth + barWidth + 8} y={barHeight - 6} className="chart-value">
                {row.value}
              </text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}

export interface ModelBar {
  model: string;
  counts: { type: string; count: number }[];
}

export function ModelChart({ rows }: { rows: ModelBar[] }) {
  const width = 720;
  const labelWidth = 140;
  const barHeight = 22;
  const gap = 14;
  const height = Math.max(rows.length, 1) * (barHeight + gap) + 8;
  const max = Math.max(
    1,
    ...rows.map((row) => row.counts.reduce((sum, item) => sum + item.count, 0)),
  );
  const barArea = width - labelWidth - 48;

  return (
    <figure className="chart">
      <figcaption>Findings by model</figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Findings by model">
        {rows.map((row, index) => {
          const y = index * (barHeight + gap);
          const total = row.counts.reduce((sum, item) => sum + item.count, 0);
          let cursor = labelWidth;
          return (
            <g key={row.model} transform={`translate(0 ${y})`}>
              <text x={0} y={barHeight - 6} className="chart-label">
                {row.model}
              </text>
              {row.counts.map((item) => {
                const segment = (item.count / max) * barArea;
                const x = cursor;
                cursor += segment;
                return (
                  <rect
                    key={item.type}
                    x={x}
                    y={0}
                    width={segment}
                    height={barHeight}
                    fill={findingColor(item.type)}
                  >
                    <title>{`${findingLabel(item.type)}: ${item.count}`}</title>
                  </rect>
                );
              })}
              <text x={Math.max(cursor + 8, labelWidth + 8)} y={barHeight - 6} className="chart-value">
                {total}
              </text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}
