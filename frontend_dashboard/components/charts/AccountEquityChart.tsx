'use client';

import React, { useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { AccountEquityPoint } from '@/types/api';
import { AccountEquityChartSkeleton } from '@/components/dashboard/skeletons/AccountEquityChartSkeleton';

const INTERVALS = ['1H', '4H', '1D', '1W', 'ALL'];

export default function AccountEquityChart() {
  const [interval, setInterval] = useState('1D');

  const { data, isLoading } = useQuery({
    queryKey: ['chart-history', interval],
    queryFn: () => api.getChartHistory(interval),
    refetchInterval: 30000, // 30s polling
  });

  if (isLoading) {
    // 骨架布局与真实图表的父容器一致，避免加载时布局跳动
    return <AccountEquityChartSkeleton />;
  }

  const getOption = (chartData: AccountEquityPoint[]) => {
    if (!chartData || chartData.length === 0) return {};

    const dates = chartData.map(d => d.timestamp);
    const values = chartData.map(d => d.equity);

    // Calculate daily returns for the bar chart if needed, 
    // or just show simple equity curve.
    // Here we implement the requirement: "Main chart line + area, bottom small bar chart"
    
    // Simple PnL calc for the bar chart
    const pnl = chartData.map((d, i) => {
        if (i === 0) return 0;
        return d.equity - chartData[i-1].equity;
    });

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        formatter: (params: any) => {
          // Custom tooltip showing Value + Change
          const equityParam = params[0];
          if (!equityParam) return '';
          
          // Find the index to calculate change
          const index = equityParam.dataIndex;
          const currentVal = values[index];
          const prevVal = index > 0 ? values[index - 1] : currentVal;
          const change = currentVal - prevVal;
          const changePct = prevVal !== 0 ? (change / prevVal) * 100 : 0;
          
          let html = `<div class="font-sans text-sm">
            <div class="text-slate-400 mb-1">${equityParam.axisValue}</div>
            <div class="flex justify-between gap-4">
              <span>Equity:</span>
              <span class="font-bold text-slate-100">$${currentVal.toLocaleString(undefined, {minimumFractionDigits: 2})}</span>
            </div>
            <div class="flex justify-between gap-4 mt-1">
              <span>Change:</span>
              <span class="${change >= 0 ? 'text-green-400' : 'text-red-400'}">
                ${change >= 0 ? '+' : ''}${change.toFixed(2)} (${changePct.toFixed(2)}%)
              </span>
            </div>
          </div>`;
          return html;
        }
      },
      grid: [
        { left: 20, right: 16, height: '65%', top: '10%', containLabel: true },
        { left: 20, right: 16, top: '80%', height: '15%', containLabel: true }
      ],
      xAxis: [
        {
          type: 'category',
          data: dates,
          boundaryGap: false,
          axisLine: { lineStyle: { color: '#475569' } },
          axisLabel: { color: '#94a3b8' }
        },
        {
          type: 'category',
          gridIndex: 1,
          data: dates,
          boundaryGap: false,
          axisLine: { show: false },
          axisLabel: { show: false },
          axisTick: { show: false }
        }
      ],
      yAxis: [
        {
          type: 'value',
          scale: true, // Auto scale
          splitLine: { lineStyle: { color: '#334155', type: 'dashed' } },
          axisLabel: { color: '#94a3b8' }
        },
        {
          type: 'value',
          gridIndex: 1,
          scale: true,
          splitLine: { show: false },
          axisLabel: { show: false }
        }
      ],
      series: [
        {
            name: 'Equity',
            type: 'line',
            data: values,
            smooth: true,
            symbol: 'none',
            lineStyle: { width: 3, color: '#3b82f6' }, // Blue-500
            areaStyle: {
                color: {
                    type: 'linear',
                    x: 0, y: 0, x2: 0, y2: 1,
                    colorStops: [
                        { offset: 0, color: 'rgba(59, 130, 246, 0.5)' },
                        { offset: 1, color: 'rgba(59, 130, 246, 0.0)' }
                    ]
                }
            }
        },
        {
            name: 'PnL',
            type: 'bar',
            xAxisIndex: 1,
            yAxisIndex: 1,
            data: pnl.map(v => ({
                value: v,
                itemStyle: {
                    color: v >= 0 ? '#10b981' : '#ef4444' // Green / Red
                }
            }))
        }
      ]
    };
  };

  return (
    <div className="w-full h-full min-h-[560px] xl:min-h-[600px] flex flex-col bg-slate-900 rounded-xl border border-slate-800 p-4 shadow-xl">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-slate-100 font-semibold text-lg flex items-center gap-2">
            <span className="w-2 h-6 bg-blue-500 rounded-sm"></span>
            Account Equity
        </h3>
        <div className="flex gap-1 bg-slate-950 p-1 rounded-lg">
          {INTERVALS.map(int => (
            <button
              key={int}
              onClick={() => setInterval(int)}
              className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                interval === int 
                ? 'bg-slate-800 text-blue-400' 
                : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              {int}
            </button>
          ))}
        </div>
      </div>
      
      <div className="flex-1 min-h-[300px]">
        {isLoading ? (
           <div className="h-full w-full flex items-center justify-center text-slate-500">Loading Chart...</div>
        ) : (
           <ReactECharts 
             option={getOption(data || [])} 
             style={{ height: '100%', width: '100%' }}
             theme="dark" // assuming echarts registered theme or using default dark-ish
           />
        )}
      </div>
    </div>
  );
}
