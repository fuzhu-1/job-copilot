export function Panel({ title, desc, actions, children, className = '', pad = 'p-5' }) {
  return (
    <section className={`bg-white border border-slate-200 rounded-2xl shadow-[0_1px_2px_rgba(15,23,42,0.05)] ${pad} ${className}`}>
      {(title || actions) && (
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            {title && (
              <h2 className="text-[15px] font-semibold tracking-tight text-slate-900">{title}</h2>
            )}
            {desc && <p className="mt-0.5 text-xs text-slate-500">{desc}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  )
}

export function Btn({
  variant = 'primary',
  size = 'md',
  className = '',
  ...props
}) {
  const base =
    'inline-flex items-center justify-center gap-1.5 rounded-lg font-medium ' +
    'transition-[background-color,box-shadow,transform] duration-150 active:scale-[0.97] ' +
    'disabled:pointer-events-none disabled:opacity-50'
  const variants = {
    primary: 'bg-indigo-600 text-white shadow-sm hover:bg-indigo-500',
    ghost: 'bg-slate-100 text-slate-700 hover:bg-slate-200',
    dark: 'bg-slate-800 text-white hover:bg-slate-700',
    success: 'bg-emerald-600 text-white shadow-sm hover:bg-emerald-500',
    danger: 'bg-rose-600 text-white shadow-sm hover:bg-rose-500',
  }
  const sizes = { sm: 'h-8 px-3 text-xs', md: 'h-10 px-4 text-sm' }
  return (
    <button className={`${base} ${variants[variant]} ${sizes[size]} ${className}`} {...props} />
  )
}

export function Chip({ tone = 'slate', children, className = '' }) {
  const tones = {
    slate: 'bg-slate-100 text-slate-700',
    blue: 'bg-blue-50 text-blue-700',
    indigo: 'bg-indigo-50 text-indigo-700',
    green: 'bg-emerald-50 text-emerald-700',
    amber: 'bg-amber-50 text-amber-700',
    rose: 'bg-rose-50 text-rose-700',
    dark: 'bg-slate-800 text-slate-100',
  }
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  )
}

export const inputCls =
  'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 ' +
  'placeholder:text-slate-400 transition-[border-color,box-shadow] duration-150 ' +
  'focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/25'

export const labelCls = 'mb-1.5 block text-xs font-medium text-slate-500'

export function EmptyState({ icon, title, desc }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50/60 px-6 py-10 text-center">
      {icon && <div className="mb-3 text-slate-400">{icon}</div>}
      <p className="text-sm font-medium text-slate-600">{title}</p>
      {desc && <p className="mt-1 max-w-sm text-xs text-slate-400">{desc}</p>}
    </div>
  )
}

export function plainText(s) {
  return (s || '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/\*\*/g, '')
    .replace(/^#{1,6}\s*/gm, '')
    .replace(/^\s*[-•]\s*/gm, '')
}
