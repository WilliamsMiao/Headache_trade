import Link from "next/link";

export default function Header() {
  return (
    <header className="flex flex-col md:flex-row justify-between items-start md:items-center p-6 border-b border-slate-800 bg-slate-950/80 backdrop-blur-md sticky top-0 z-50">
      <div>
        <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-indigo-500">
          Headache Trade <span className="text-slate-500 font-light text-lg">AI Dashboard</span>
        </h1>
        <div className="flex items-center gap-2 mt-1">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
          <p className="text-xs text-slate-400">System Operational</p>
        </div>
      </div>

      <div className="flex items-center gap-6 mt-4 md:mt-0">
        <Link
          href="/dashboard/control"
          className="hidden md:inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-700 bg-slate-900 text-slate-100 hover:border-blue-500 hover:text-white transition text-sm font-semibold"
        >
          控制中心
        </Link>
      </div>
    </header>
  );
}
