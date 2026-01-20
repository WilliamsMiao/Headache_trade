import DashboardClient from "@/components/dashboard/dashboard-client";
import { DashboardResponse } from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:5001/api";

async function getDashboardData(): Promise<DashboardResponse> {
  const res = await fetch(`${API_BASE}/dashboard`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error("Failed to fetch dashboard data");
  }

  return res.json();
}

export default async function DashboardPage() {
  const data = await getDashboardData();

  return <DashboardClient initialData={data} />;
}
