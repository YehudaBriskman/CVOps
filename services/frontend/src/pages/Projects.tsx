export default function Projects() {
  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-ink">Projects</h2>
          <p className="text-sm text-mist mt-0.5">Each project is one ML problem domain</p>
        </div>
        <button
          disabled
          className="bg-cobalt text-white px-4 py-2 rounded-lg text-sm font-medium opacity-60 cursor-not-allowed"
        >
          + New Project
        </button>
      </div>

      <div className="rounded-xl border border-cloud bg-white shadow-sm p-10 text-center">
        <p className="text-sm font-medium text-ink">No projects yet</p>
        <p className="text-xs text-mist mt-1">
          Project listing will appear here once the projects API is wired up.
        </p>
      </div>
    </div>
  )
}
