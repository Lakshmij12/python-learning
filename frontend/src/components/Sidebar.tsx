"use client";

// Dashboard navigation. Sections mirror the product's feature set; each links
// to a route that will render the corresponding view.
const SECTIONS = [
  "Overview",
  "Conversations",
  "Memory",
  "Search",
  "Notes",
  "Tasks",
  "Calendar",
  "Files",
  "Analytics",
  "Prompt Manager",
  "Models",
  "Settings",
  "Logs",
  "Health",
  "API Usage",
];

export function Sidebar({ active = "Overview" }: { active?: string }) {
  return (
    <aside className="w-56 shrink-0 border-r border-gray-200 bg-white p-4">
      <div className="mb-6 flex items-center gap-2">
        <span className="text-xl">🤖</span>
        <span className="font-semibold">Assistant</span>
      </div>
      <nav className="space-y-1">
        {SECTIONS.map((s) => (
          <a
            key={s}
            href={`/${s.toLowerCase().replace(/\s+/g, "-")}`}
            className={`block rounded px-3 py-2 text-sm ${
              s === active ? "bg-brand/10 font-medium text-brand-dark" : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            {s}
          </a>
        ))}
      </nav>
    </aside>
  );
}
