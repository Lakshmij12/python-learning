"use client";

import { useEffect, useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { api, getToken } from "@/lib/api";

interface Task {
  id: string;
  title: string;
  status: string;
}

export default function OverviewPage() {
  const [email, setEmail] = useState<string>("");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [health, setHealth] = useState<string>("…");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    if (!getToken()) {
      window.location.href = "/login";
      return;
    }
    api.me().then((u) => setEmail(u.email)).catch((e) => setError(e.message));
    api.tasks().then(setTasks).catch(() => {});
    api.health().then((h) => setHealth(h.status)).catch(() => setHealth("unreachable"));
  }, []);

  return (
    <div className="flex min-h-screen">
      <Sidebar active="Overview" />
      <main className="flex-1 p-8">
        <header className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">Overview</h1>
            <p className="text-sm text-gray-500">{email && `Signed in as ${email}`}</p>
          </div>
          <span className="rounded-full bg-brand/10 px-3 py-1 text-sm text-brand-dark">
            API: {health}
          </span>
        </header>

        {error && <p className="mb-4 rounded bg-red-50 p-3 text-sm text-red-700">{error}</p>}

        <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard label="Open tasks" value={tasks.filter((t) => t.status !== "done").length} />
          <StatCard label="Total tasks" value={tasks.length} />
          <StatCard label="Health" value={health} />
        </section>

        <section className="mt-8">
          <h2 className="mb-3 text-lg font-medium">Recent tasks</h2>
          <ul className="divide-y rounded border bg-white">
            {tasks.length === 0 && <li className="p-4 text-sm text-gray-500">No tasks yet.</li>}
            {tasks.map((t) => (
              <li key={t.id} className="flex items-center justify-between p-3 text-sm">
                <span>{t.title}</span>
                <span className="rounded bg-gray-100 px-2 py-0.5 text-xs">{t.status}</span>
              </li>
            ))}
          </ul>
        </section>
      </main>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border bg-white p-5">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}
