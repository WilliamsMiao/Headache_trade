"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { TradingParameters, BacktestJob, ConfigHistoryEntry, LogEntry } from "@/types/api";

const StatCard = ({ title, value, hint }: { title: string; value: React.ReactNode; hint?: string }) => (
  <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col gap-2 shadow-lg">
    <div className="text-xs uppercase tracking-wide text-slate-500 flex items-center gap-2">{title}{hint && <span className="text-[10px] text-slate-600">{hint}</span>}</div>
    <div className="text-xl font-semibold text-slate-100">{value}</div>
  </div>
);

const Section = ({ title, children, actions }: { title: string; children: React.ReactNode; actions?: React.ReactNode }) => (
  <div className="bg-slate-950/60 border border-slate-800 rounded-2xl p-4 md:p-5 shadow-xl space-y-4">
    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
      <h2 className="text-lg font-semibold text-slate-100 tracking-tight">{title}</h2>
      {actions}
    </div>
    {children}
  </div>
);

export default function ControlCenterPage() {
  const queryClient = useQueryClient();
  const [logType, setLogType] = useState<string>("bot");
  const [autoScroll, setAutoScroll] = useState<boolean>(true);
  const logContainerRef = useRef<HTMLDivElement | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logError, setLogError] = useState<string | null>(null);

  const paramsQuery = useQuery({
    queryKey: ["trading-params"],
    queryFn: () => api.getTradingParams(),
    refetchInterval: 5000,
  });

  const historyQuery = useQuery({
    queryKey: ["config-history"],
    queryFn: () => api.getConfigHistory(),
    refetchInterval: 10000,
  });

  const [form, setForm] = useState({
    days: 30,
    config: "default",
    ai_feedback: false,
    initial_balance: 100,
    leverage: 6,
  });

  const backtestMutation = useMutation({
    mutationFn: api.runBacktest,
    onSuccess: (job: BacktestJob) => {
      setLastJob(job);
    },
  });

  const rollbackMutation = useMutation({
    mutationFn: api.rollbackConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["config-history"] });
      queryClient.invalidateQueries({ queryKey: ["trading-params"] });
    },
  });

  const [lastJob, setLastJob] = useState<BacktestJob | null>(null);

  useEffect(() => {
    if (autoScroll && logs.length && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  useEffect(() => {
    let cancelled = false;
    let es: EventSource | null = null;

    const prime = async () => {
      try {
        const initial = await api.getLogs({ type: logType, limit: 200 });
        if (!cancelled) {
          setLogs(initial);
          setLogError(null);
        }
      } catch (err) {
        if (!cancelled) setLogError("日志获取失败，使用回退数据");
      }
    };

    prime();

    try {
      es = new EventSource(`/api/logs/stream?type=${logType}`);
      es.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as LogEntry;
          setLogs((prev) => [...prev.slice(-199), payload]);
        } catch (err) {
          // ignore bad frames
        }
      };
      es.onerror = () => {
        setLogError("日志流中断，已停用SSE");
        if (es) {
          es.close();
        }
      };
    } catch (err) {
      setLogError("SSE初始化失败，已停用SSE");
    }

    return () => {
      cancelled = true;
      if (es) es.close();
    };
  }, [logType]);

  const protectionLevels = useMemo(() => {
    const params = paramsQuery.data as TradingParameters | undefined;
    if (!params) return [];
    return Object.entries(params.protection.protection_levels).map(([key, val]) => ({
      key,
      ...val,
    }));
  }, [paramsQuery.data]);

  const runBacktest = () => {
    backtestMutation.mutate({
      days: form.days,
      config: form.config || undefined,
      ai_feedback: form.ai_feedback,
      initial_balance: form.initial_balance,
      leverage: form.leverage,
    });
  };

  const params = paramsQuery.data;

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-950 to-slate-900 text-slate-200">
      <div className="max-w-7xl mx-auto px-4 md:px-6 py-6 space-y-6">
        <div className="flex flex-col gap-3">
          <p className="text-sm uppercase tracking-[0.2em] text-blue-400">Control Center</p>
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
            <h1 className="text-2xl md:text-3xl font-bold text-white">交易参数 · 回测 · 日志</h1>
            <div className="text-sm text-slate-400">实时参数总览 · 一键回测（可选AI反思迭代） · 日志监控</div>
          </div>
        </div>

        <Section
          title="实时交易参数"
          actions={
            <button
              onClick={() => queryClient.invalidateQueries({ queryKey: ["trading-params"] })}
              className="px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-sm hover:border-blue-500 hover:text-white transition"
            >
              刷新
            </button>
          }
        >
          {paramsQuery.isLoading ? (
            <div className="text-slate-500">加载中...</div>
          ) : paramsQuery.isError ? (
            <div className="text-red-400">加载失败，使用回退数据</div>
          ) : null}

          {params && (
            <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-4 gap-4">
              <StatCard title="交易对" value={params.symbol} />
              <StatCard title="时间周期" value={params.timeframe} />
              <StatCard title="杠杆" value={`${params.leverage}x`} />
              <StatCard title="手续费" value={(params.fee_rate * 100).toFixed(2) + "%"} />
              <StatCard title="滑点" value={(params.slippage * 100).toFixed(2) + "%"} />
              <StatCard title="基础风险/单" value={(params.risk.base_risk_per_trade * 100).toFixed(1) + "%"} />
              <StatCard title="目标资金利用率" value={(params.risk.target_utilization * 100).toFixed(0) + "%"} />
              <StatCard title="最大资金利用率" value={(params.risk.max_utilization * 100).toFixed(0) + "%"} />
              <StatCard title="最大杠杆" value={`${params.risk.max_leverage}x`} />
              <StatCard title="锁盈触发" value={(params.risk.lock_stop_loss_profit_threshold * 100).toFixed(1) + "%"} hint="启动锁定止损" />
              <StatCard title="锁盈比例" value={(params.risk.lock_stop_loss_ratio * 100).toFixed(0) + "%"} />
              <StatCard title="自适应风险" value={params.risk.adaptive_risk_enabled ? "ON" : "OFF"} />
            </div>
          )}

          {params && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {protectionLevels.map(level => (
                <div key={level.key} className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
                  <div className="text-sm font-semibold text-white capitalize">{level.key}</div>
                  <div className="text-xs text-slate-400">激活: {level.activation_time}s</div>
                  <div className="flex gap-3 text-sm text-slate-200">
                    <span>TP x{level.take_profit_multiplier}</span>
                    <span>SL x{level.stop_loss_multiplier}</span>
                  </div>
                  {level.min_profit_required !== undefined && (
                    <div className="text-xs text-slate-500">最小盈利: {(level.min_profit_required * 100).toFixed(2)}%</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Section>

        <Section
          title="一键运行回测"
          actions={
            <div className="flex items-center gap-3 text-sm text-slate-400">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={form.ai_feedback}
                  onChange={e => setForm(f => ({ ...f, ai_feedback: e.target.checked }))}
                  className="accent-blue-500"
                />
                启用AI反思自动迭代
              </label>
            </div>
          }
        >
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div className="col-span-1 md:col-span-1">
              <label className="text-sm text-slate-400">数据天数</label>
              <input
                type="number"
                value={form.days}
                onChange={e => setForm(f => ({ ...f, days: Number(e.target.value) || 1 }))}
                className="w-full mt-1 bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-slate-100 focus:border-blue-500 focus:outline-none"
                min={1}
                max={120}
              />
            </div>
            <div className="col-span-1 md:col-span-1">
              <label className="text-sm text-slate-400">初始资金 (USDT)</label>
              <input
                type="number"
                value={form.initial_balance}
                onChange={e => setForm(f => ({ ...f, initial_balance: Number(e.target.value) || 0 }))}
                className="w-full mt-1 bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-slate-100 focus:border-blue-500 focus:outline-none"
                min={10}
                step={10}
              />
            </div>
            <div className="col-span-1 md:col-span-1">
              <label className="text-sm text-slate-400">杠杆</label>
              <input
                type="number"
                value={form.leverage}
                onChange={e => setForm(f => ({ ...f, leverage: Number(e.target.value) || 1 }))}
                className="w-full mt-1 bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-slate-100 focus:border-blue-500 focus:outline-none"
                min={1}
                max={50}
              />
            </div>
            <div className="col-span-1 md:col-span-1">
              <label className="text-sm text-slate-400">配置名</label>
              <input
                type="text"
                value={form.config}
                onChange={e => setForm(f => ({ ...f, config: e.target.value }))}
                className="w-full mt-1 bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-slate-100 focus:border-blue-500 focus:outline-none"
                placeholder="default 或自定义"
              />
            </div>
            <div className="flex items-end">
              <button
                onClick={runBacktest}
                disabled={backtestMutation.isPending}
                className="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold px-4 py-3 rounded-lg shadow-lg disabled:opacity-60 disabled:cursor-not-allowed transition"
              >
                {backtestMutation.isPending ? "运行中..." : "一键运行"}
              </button>
            </div>
          </div>

          {lastJob && (
            <div className="mt-4 grid grid-cols-1 md:grid-cols-4 gap-3 text-sm">
              <StatCard title="任务ID" value={lastJob.id} />
              <StatCard title="状态" value={lastJob.status} />
              <StatCard title="收益率" value={lastJob.total_return_pct !== undefined ? `${lastJob.total_return_pct.toFixed(2)}%` : "-"} />
              <StatCard title="AI反思" value={lastJob.ai_feedback ? "启用" : "关闭"} />
            </div>
          )}
          {backtestMutation.isError && (
            <div className="text-red-400 text-sm">回测触发失败，已返回演示结果</div>
          )}
        </Section>

        <Section
          title="配置历史"
          actions={
            <button
              onClick={() => historyQuery.refetch()}
              className="px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-sm hover:border-blue-500 hover:text-white transition"
            >
              刷新
            </button>
          }
        >
          {historyQuery.isLoading && <div className="text-slate-500">加载历史...</div>}
          {historyQuery.isError && <div className="text-red-400">历史获取失败</div>}
          {historyQuery.data && historyQuery.data.length === 0 && (
            <div className="text-slate-500">暂无历史记录</div>
          )}
          {historyQuery.data && historyQuery.data.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
              {historyQuery.data.map((item: ConfigHistoryEntry) => (
                <div key={item.name} className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
                  <div className="text-sm font-semibold text-white break-all">{item.name}</div>
                  <div className="text-xs text-slate-500">{item.timestamp}</div>
                  <div className="flex items-center justify-between text-sm text-slate-300">
                    <span>{item.size ? `${(item.size / 1024).toFixed(1)} KB` : ""}</span>
                    <button
                      onClick={() => rollbackMutation.mutate(item.name)}
                      disabled={rollbackMutation.isPending}
                      className="px-3 py-1 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-xs disabled:opacity-60"
                    >
                      回滚
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Section>

        <Section
          title="实时日志"
          actions={
            <div className="flex items-center gap-3 text-sm text-slate-400">
              <div className="flex bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
                {[
                  { key: "bot", label: "Bot" },
                  { key: "dashboard", label: "Dashboard" },
                  { key: "commander", label: "Commander" },
                  { key: "backtest", label: "Backtest" },
                ].map(tab => (
                  <button
                    key={tab.key}
                    onClick={() => setLogType(tab.key)}
                    className={`px-3 py-2 border-r border-slate-800 last:border-r-0 ${logType === tab.key ? "bg-blue-600 text-white" : "text-slate-300 hover:bg-slate-800"}`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={autoScroll}
                  onChange={e => setAutoScroll(e.target.checked)}
                  className="accent-blue-500"
                />
                自动滚动
              </label>
            </div>
          }
        >
          <div
            ref={logContainerRef}
            className="bg-slate-900 border border-slate-800 rounded-xl p-4 h-[360px] overflow-auto font-mono text-xs leading-6 text-slate-100"
          >
            {!logs.length && <div className="text-slate-500">加载日志...</div>}
            {logError && <div className="text-red-400">{logError}</div>}
            {logs.map((log, idx) => (
              <div key={idx} className="flex gap-3">
                <span className="text-slate-500 min-w-[160px]">{log.timestamp}</span>
                <span className={`min-w-[64px] ${log.level === "WARN" ? "text-amber-400" : "text-emerald-400"}`}>{log.level}</span>
                <span className="min-w-[90px] text-slate-400">[{log.source}]</span>
                <span className="text-slate-100">{log.message}</span>
              </div>
            ))}
          </div>
        </Section>
      </div>
    </div>
  );
}
