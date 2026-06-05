import { useEffect, useRef } from "react";
import { echarts } from "@/lib/echarts";
import { getChartTheme } from "@/lib/chart-theme";

interface TrendPoint {
  t: number | null;
  p: number | null;
}

interface Props {
  points: TrendPoint[];
  height?: number;
}

/** Line chart of an outcome's Yes-probability (%) over time. */
export function ProbabilityTrend({ points, height = 280 }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || points.length === 0) return;

    const t = getChartTheme();
    const chart = echarts.init(ref.current);

    const rows = points
      .filter((d): d is { t: number; p: number } => typeof d.t === "number" && typeof d.p === "number")
      .map((d) => {
        const date = new Date(d.t * 1000);
        return { label: `${date.getMonth() + 1}/${date.getDate()}`, value: +(d.p * 100).toFixed(1) };
      });

    chart.setOption({
      backgroundColor: "transparent",
      grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
      tooltip: {
        trigger: "axis",
        backgroundColor: t.tooltipBg,
        borderColor: t.tooltipBorder,
        textStyle: { color: t.tooltipText, fontSize: 12 },
        valueFormatter: (v: unknown) => `${v}%`,
      },
      xAxis: {
        type: "category",
        data: rows.map((r) => r.label),
        boundaryGap: false,
        axisLabel: { color: t.textColor, fontSize: 11 },
        axisLine: { lineStyle: { color: t.axisColor } },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 100,
        axisLabel: { color: t.textColor, fontSize: 11, formatter: "{value}%" },
        splitLine: { lineStyle: { color: t.gridColor } },
      },
      series: [
        {
          name: "Yes 概率",
          type: "line",
          smooth: true,
          showSymbol: false,
          data: rows.map((r) => r.value),
          lineStyle: { color: t.infoColor, width: 2 },
          areaStyle: { color: t.infoColor + "22" },
        },
      ],
    });

    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(ref.current);
    return () => { ro.disconnect(); chart.dispose(); };
  }, [points]);

  if (points.length === 0) {
    return <div className="text-muted-foreground text-sm p-4">暂无趋势数据</div>;
  }
  return <div ref={ref} style={{ height }} />;
}
