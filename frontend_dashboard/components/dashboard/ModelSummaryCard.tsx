'use client';

import React from 'react';
import { DeltaFlash } from '@/components/ui/DeltaFlash';
import { DeepSeekModelData } from '@/types/api';

export default function ModelSummaryCard({ modelData }: { modelData: DeepSeekModelData }) {
  if (!modelData) return null;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl relative overflow-hidden group hover:border-slate-700 transition-colors h-full">
      <div className="absolute top-0 right-0 p-4 opacity-50">
        <div className={`w-3 h-3 rounded-full ${modelData.status === 'active' ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
      </div>
      
      <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-lg bg-indigo-500/20 flex items-center justify-center text-indigo-300 font-bold text-lg">
            AI
          </div>
        <div>
            <h3 className="text-slate-100 font-bold hover-data inline-flex items-center">{modelData.name}</h3>
            <p className="text-xs text-slate-500 hover-data inline-flex items-center">Last updated: {modelData.last_update.split(' ')[1]}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
            <p className="text-xs text-slate-400 mb-1">Account Value</p>
            <DeltaFlash value={modelData.account_value} className="text-2xl font-bold text-slate-50 tracking-tight hover-data inline-flex items-center">
              ${modelData.account_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </DeltaFlash>
        </div>
        <div>
            <p className="text-xs text-slate-400 mb-1">24h Change</p>
            <DeltaFlash value={modelData.change_percent} className={`text-2xl font-bold tracking-tight hover-data inline-flex items-center ${modelData.change_percent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {modelData.change_percent >= 0 ? '+' : ''}{modelData.change_percent}%
            </DeltaFlash>
        </div>
      </div>
    </div>
  );
}
