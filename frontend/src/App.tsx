import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { api } from './api';
import type { Activity, Category, Snack, SnackPage, StockStatus, Summary, User } from './types';

type View = 'pantry' | 'activity';
type SnackForm = { name: string; category: Category; quantity: number; low_stock_threshold: number };
type Dialog = { kind: 'add' } | { kind: 'edit'; snack: Snack } | { kind: 'consume' | 'restock' | 'delete'; snack: Snack } | null;
type Notice = { message: string; kind: 'success' | 'error' } | null;

const emoji: Record<Category, string> = { sweet: '🍪', savoury: '🥨', drink: '🧃', 'healthy-ish': '🥜' };
const label: Record<StockStatus, string> = { stocked: 'In stock', running_low: 'Running low', gone: 'Out of stock' };
const blankForm: SnackForm = { name: '', category: 'savoury', quantity: 0, low_stock_threshold: 5 };

function stockLabel(stock: StockStatus) { return <span className={`status status-${stock}`}><i />{label[stock]}</span>; }
function messageOf(err: unknown): string { return err instanceof Error ? err.message : 'Something went wrong. Please try again.'; }
function formatDate(value: string) { return new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }); }
function markIcon(kind: string) {
  const icons: Record<string, string> = { box: '▦', low: '◔', gone: '○', total: '◫', star: '★' };
  return icons[kind] || '●';
}

function Login({ onLogin }: { onLogin: (token: string, user: User) => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('member@snackoverflow.dev');
  const [password, setPassword] = useState('Member123!');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const registering = mode === 'register';

  function changeMode(next: 'login' | 'register') {
    setMode(next);
    setError('');
    setName('');
    setEmail(next === 'login' ? 'member@snackoverflow.dev' : '');
    setPassword(next === 'login' ? 'Member123!' : '');
    setConfirmPassword('');
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError('');
    if (registering && password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      const data = registering
        ? await api.register(name.trim(), email.trim(), password)
        : await api.login(email.trim(), password);
      onLogin(data.token, data.user);
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setLoading(false);
    }
  }

  return <div className="login-page">
    <div className="login-art">
      <div className="logo-brand"><span className="brand-dot">bpf<span>.</span></span><span className="brand-rule"/> OFFICE PANTRY</div>
      <div className="login-art-body">
        <p className="eyebrow dark-eyebrow">THE SNACK SITUATION, SORTED.</p>
        <h1>Good snacks.<br /><em>Great tracking.</em></h1>
        <p>Know what’s left, save your favourites, and never lose the last packet to a spreadsheet again.</p>
        <div className="snack-illustration" aria-hidden="true"><div className="illustration-halo"/><span className="illo-cookie">🍪</span><span className="illo-chip">🍟</span><span className="illo-drink">🧃</span><span className="illo-spark one">✦</span><span className="illo-spark two">✳</span></div>
      </div>
      <div className="art-foot">MADE FOR THE HUNGRIEST TEAMS. &nbsp;✦ &nbsp; SNACK OVERFLOW © 2026</div>
    </div>
    <div className="login-side"><div className="login-box">
      <div className="mobile-brand">bpf<span>.</span></div>
      <div className="login-badge">🍿 &nbsp; {registering ? 'Join the office pantry' : 'Welcome to the pantry'}</div>
      <h2>{registering ? <>Create your<br />member account</> : <>Sign in to<br />Snack Overflow</>}<span className="period">.</span></h2>
      <p className="muted intro">{registering ? 'Sign up to browse, vote for, and enjoy office snacks.' : 'Your office pantry, all in one place.'}</p>
      <form onSubmit={submit}>
        {registering && <>
          <label className="form-label" htmlFor="register-name">Full name</label>
          <input id="register-name" autoComplete="name" minLength={2} maxLength={120} required value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Sam Taylor" />
        </>}
        <label className="form-label" htmlFor="email">Email</label>
        <input id="email" autoComplete="email" type="email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="you@company.com" />
        <label className="form-label" htmlFor="password">Password</label>
        <input id="password" type="password" autoComplete={registering ? 'new-password' : 'current-password'} minLength={registering ? 8 : undefined} maxLength={registering ? 128 : undefined} required value={password} onChange={e => setPassword(e.target.value)} />
        {registering && <>
          <p className="register-hint">At least 8 characters, including one letter and one number.</p>
          <label className="form-label" htmlFor="confirm-password">Confirm password</label>
          <input id="confirm-password" type="password" autoComplete="new-password" required value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} />
        </>}
        {error && <div className="inline-error" role="alert">⚠ {error}</div>}
        <button className="primary login-submit" type="submit" disabled={loading}>{loading ? (registering ? 'Creating account…' : 'Signing in…') : (registering ? 'Create member account →' : 'Sign in to pantry →')}</button>
      </form>
      <p className="auth-switch">{registering ? 'Already have an account?' : 'New to Snack Overflow?'}{' '}
        <button type="button" disabled={loading} onClick={() => changeMode(registering ? 'login' : 'register')}>{registering ? 'Sign in' : 'Create an account'}</button>
      </p>
      {!registering && <div className="demo-box"><strong>🪄 &nbsp; Try a demo account</strong><p>Choose a role to see different permissions.</p>
        <div className="demo-actions"><button type="button" onClick={() => { setEmail('member@snackoverflow.dev'); setPassword('Member123!'); }}>👋 Member</button><button type="button" onClick={() => { setEmail('admin@snackoverflow.dev'); setPassword('Admin123!'); }}>⚙ Admin</button></div>
      </div>}
    </div><div className="login-footer">Built for Bipolar Factory · Round 2 Internship Assignment</div></div>
  </div>;
}

function DialogShell({ title, subtitle, children, onClose }: { title: string; subtitle: string; children: ReactNode; onClose: () => void }) {
  return <div className="modal-backdrop" role="presentation" onMouseDown={e => { if (e.currentTarget === e.target) onClose(); }}>
    <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
      <button type="button" className="modal-close" onClick={onClose} aria-label="Close dialog">×</button>
      <h2>{title}</h2><p className="muted modal-subtitle">{subtitle}</p>{children}
    </div>
  </div>;
}

function SnackDialog({ dialog, onClose, onSave }: { dialog: NonNullable<Dialog>; onClose: () => void; onSave: (dialog: NonNullable<Dialog>, values?: SnackForm | number) => Promise<void> }) {
  const initial = dialog.kind === 'edit' ? { name: dialog.snack.name, category: dialog.snack.category, quantity: dialog.snack.quantity, low_stock_threshold: dialog.snack.low_stock_threshold } : blankForm;
  const [form, setForm] = useState<SnackForm>(initial);
  const [amount, setAmount] = useState(1);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const change = (key: keyof SnackForm, value: string | number) => setForm(old => ({ ...old, [key]: value }));
  const isForm = dialog.kind === 'add' || dialog.kind === 'edit';
  const title = dialog.kind === 'add' ? 'Add a new snack' : dialog.kind === 'edit' ? 'Edit snack' : dialog.kind === 'consume' ? 'Grab a snack' : dialog.kind === 'restock' ? 'Restock the pantry' : 'Remove this snack?';
  const subtitle = dialog.kind === 'add' ? 'Give the team something new to look forward to.' : dialog.kind === 'edit' ? `Update details for ${dialog.snack.name}.` : dialog.kind === 'consume' ? `There are ${dialog.snack.quantity} × ${dialog.snack.name} available right now.` : dialog.kind === 'restock' ? `Add more ${dialog.snack.name} to your inventory.` : `This permanently removes ${dialog.snack.name} from the pantry. Past activity is preserved.`;
  async function submit(e: FormEvent) {
    e.preventDefault();
    setSaving(true); setError('');
    try { await onSave(dialog, isForm ? form : amount); onClose(); }
    catch (err) { setError(messageOf(err)); }
    finally { setSaving(false); }
  }
  return <DialogShell title={title} subtitle={subtitle} onClose={onClose}>
    <form onSubmit={submit}>
      {isForm ? <>
        <label className="form-label" htmlFor="snack-name">Snack name</label>
        <input id="snack-name" value={form.name} maxLength={120} required onChange={e => change('name', e.target.value)} placeholder="e.g. Salted caramel popcorn" autoFocus />
        <label className="form-label" htmlFor="snack-category">Category</label>
        <select id="snack-category" value={form.category} onChange={e => change('category', e.target.value)}><option value="sweet">🍪 Sweet</option><option value="savoury">🥨 Savoury</option><option value="drink">🧃 Drink</option><option value="healthy-ish">🥜 Healthy-ish</option></select>
        {dialog.kind === 'add' && <><label className="form-label" htmlFor="snack-quantity">Starting quantity</label><input id="snack-quantity" type="number" min="0" max="1000000" required value={form.quantity} onChange={e => change('quantity', Number(e.target.value))} /></>}
        <label className="form-label" htmlFor="snack-threshold">Low-stock alert threshold</label>
        <input id="snack-threshold" type="number" min="0" max="1000000" required value={form.low_stock_threshold} onChange={e => change('low_stock_threshold', Number(e.target.value))} />
        {dialog.kind === 'edit' && <p className="helper">Stock quantity is adjusted using Consume / Restock so changes are audited.</p>}
      </> : dialog.kind === 'delete' ? <div className="delete-alert">⚠️ This action cannot be undone.</div> : <>
        <label className="form-label" htmlFor="amount">Number of packets</label>
        <input id="amount" type="number" min="1" max={dialog.kind === 'consume' ? Math.max(dialog.snack.quantity, 1) : 1000000} required value={amount} onChange={e => setAmount(Number(e.target.value))} autoFocus />
        {dialog.kind === 'consume' && <p className="helper">Inventory is checked again by the server when you confirm.</p>}
      </>}
      {error && <div className="inline-error" role="alert">⚠ {error}</div>}
      <div className="dialog-actions"><button type="button" className="secondary" onClick={onClose}>Cancel</button><button className={dialog.kind === 'delete' ? 'danger-button' : 'primary'} disabled={saving} type="submit">{saving ? 'Saving…' : dialog.kind === 'add' ? 'Add snack' : dialog.kind === 'edit' ? 'Save changes' : dialog.kind === 'consume' ? 'Confirm consume' : dialog.kind === 'restock' ? 'Add to stock' : 'Delete snack'}</button></div>
    </form>
  </DialogShell>;
}

function Metric({ caption, value, kind, tone }: { caption: string; value: number; kind: string; tone: string }) {
  return <div className={`metric metric-${tone}`}><div className="metric-top"><span className="metric-caption">{caption}</span><div className="metric-icon">{markIcon(kind)}</div></div><div className="metric-value">{value}</div><div className="metric-bottom">{tone === 'green' ? 'Ready for snack time' : tone === 'amber' ? 'Time to refill soon' : tone === 'red' ? 'Needs your attention' : 'Snacks in the pantry'}</div></div>;
}

function SnackCard({ snack, admin, busy, onDialog, onVote }: { snack: Snack; admin: boolean; busy: boolean; onDialog: (d: Dialog) => void; onVote: (s: Snack) => void }) {
  return <div className={`snack-card ${snack.status === 'gone' ? 'snack-out' : ''}`}>
    <div className="snack-card-main"><div className={`snack-emoji emoji-${snack.category.replace('-', '')}`}>{emoji[snack.category]}</div>
      <div className="snack-name-group"><h3 title={snack.name}>{snack.name}</h3><span className="category">{snack.category}</span></div>
      <div className="stock-column"><strong>{snack.quantity} <small>left</small></strong>{stockLabel(snack.status)}</div>
      <div className="vote-column"><button type="button" disabled={busy} aria-label={snack.has_voted ? `Remove vote for ${snack.name}` : `Vote for ${snack.name}`} className={`vote-btn ${snack.has_voted ? 'voted' : ''}`} onClick={() => onVote(snack)}>{snack.has_voted ? '♥' : '♡'} <span>{snack.votes}</span></button><small>votes</small></div>
    </div>
    <div className="snack-card-actions"><span className="stock-hint">{snack.status === 'gone' ? 'Gone for now. Come back soon!' : snack.status === 'running_low' ? '⚡ Going fast — grab yours!' : '✓ All stocked up'}</span>
      <div className="action-buttons"><button type="button" className="consume-button" disabled={busy || snack.quantity === 0} onClick={() => onDialog({ kind: 'consume', snack })}>− &nbsp; Consume</button>
      {admin && <><button type="button" className="action-restock" disabled={busy} onClick={() => onDialog({ kind: 'restock', snack })}>+ &nbsp; Restock</button><button title={`Edit ${snack.name}`} aria-label={`Edit ${snack.name}`} className="icon-btn" disabled={busy} onClick={() => onDialog({ kind: 'edit', snack })}>✎</button><button title={`Delete ${snack.name}`} aria-label={`Delete ${snack.name}`} className="icon-btn icon-danger" disabled={busy} onClick={() => onDialog({ kind: 'delete', snack })}>×</button></>}
      </div>
    </div>
  </div>;
}

function ActivityView({ token }: { token: string }) {
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<Activity[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  useEffect(() => { let active = true; setLoading(true); setError(''); api.activity(token, page).then(data => { if (active) { setItems(data.items); setTotal(data.total); setPages(data.pages); }}).catch(err => { if (active) setError(messageOf(err)); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, [token, page, reload]);
  return <section className="activity-section"><div className="section-heading"><div><p className="eyebrow">PANTRY HISTORY</p><h2>Activity log <span className="heading-count">{total}</span></h2><p className="muted">Every stock movement, accounted for.</p></div><button className="secondary" onClick={() => setReload(n => n + 1)}>↻ Refresh</button></div>
    {loading ? <div className="state-card">Loading activity…</div> : error ? <div className="state-card error-state">⚠ {error}<button className="secondary" onClick={() => setReload(n => n + 1)}>Retry</button></div> : items.length === 0 ? <div className="state-card">No activity yet. Consume or restock a snack to see the audit trail.</div> : <div className="activity-table-wrap"><table className="activity-table"><thead><tr><th>When</th><th>Who</th><th>Action</th><th>Snack</th><th>Amount</th></tr></thead><tbody>{items.map(item => <tr key={item.id}><td>{formatDate(item.created_at)}</td><td>{item.user_name}</td><td><span className={`activity-action ${item.action}`}>{item.action === 'consumed' ? '− Consumed' : '+ Restocked'}</span></td><td><strong>{item.snack_name}</strong></td><td className="tabular">{item.amount}</td></tr>)}</tbody></table></div>}
    <div className="pagination"><span>{total} recorded event{total === 1 ? '' : 's'}</span><div><button disabled={page <= 1 || loading} onClick={() => setPage(x => x - 1)}>← Previous</button><span>{pages ? `${page} / ${pages}` : '0 / 0'}</span><button disabled={page >= pages || loading} onClick={() => setPage(x => x + 1)}>Next →</button></div></div>
  </section>;
}

function Dashboard({ user, token, onLogout }: { user: User; token: string; onLogout: () => void }) {
  const isAdmin = user.role === 'admin';
  const [view, setView] = useState<View>('pantry');
  const [summary, setSummary] = useState<Summary | null>(null);
  const [snacks, setSnacks] = useState<SnackPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [filter, setFilter] = useState<StockStatus | 'all'>('all');
  const [category, setCategory] = useState<Category | 'all'>('all');
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [sort, setSort] = useState('name:asc');
  const [page, setPage] = useState(1);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const [busyIds, setBusyIds] = useState<Set<number>>(new Set());
  const requestSeq = useRef(0);

  // Every success and error toast disappears automatically after four seconds.
  // The cleanup cancels the previous timer when a new notice replaces it.
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 4000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  useEffect(() => { const timeout = window.setTimeout(() => setDebouncedQuery(query.trim()), 250); return () => window.clearTimeout(timeout); }, [query]);
  useEffect(() => { setPage(1); }, [filter, category, debouncedQuery, sort]);

  const reload = useCallback(async () => {
    const id = ++requestSeq.current;
    setLoadError(''); setLoading(true);
    const [sortBy, order] = sort.split(':');
    const params = new URLSearchParams({ page: String(page), page_size: '8', sort: sortBy, order });
    if (debouncedQuery) params.set('q', debouncedQuery);
    if (category !== 'all') params.set('category', category);
    if (filter !== 'all') params.set('status', filter);
    try {
      const [newSnacks, newSummary] = await Promise.all([api.snacks(token, params), api.summary(token)]);
      if (id !== requestSeq.current) return;
      setSnacks(newSnacks); setSummary(newSummary);
    } catch (err) {
      if (id === requestSeq.current) setLoadError(messageOf(err));
    } finally { if (id === requestSeq.current) setLoading(false); }
  }, [token, page, debouncedQuery, filter, category, sort]);
  useEffect(() => { void reload(); }, [reload]);

  async function mutate(action: () => Promise<unknown>, success: string) {
    try { await action(); setNotice({ kind: 'success', message: success }); await reload(); }
    catch (err) { setNotice({ kind: 'error', message: messageOf(err) }); await reload(); throw err; }
  }
  async function save(d: NonNullable<Dialog>, value?: SnackForm | number) {
    switch (d.kind) {
      case 'add': await mutate(() => api.create(token, value as SnackForm), 'New snack added successfully.'); break;
      case 'edit': {
        const { name, category, low_stock_threshold } = value as SnackForm;
        await mutate(() => api.edit(token, d.snack.id, { name, category, low_stock_threshold }), 'Snack details updated.'); break;
      }
      case 'consume': await mutate(() => api.consume(token, d.snack.id, value as number), 'Enjoy your snack! Inventory updated.'); break;
      case 'restock': await mutate(() => api.restock(token, d.snack.id, value as number), 'Pantry restocked successfully.'); break;
      case 'delete': await mutate(() => api.delete(token, d.snack.id), 'Snack removed from the pantry.'); break;
    }
  }
  async function vote(snack: Snack) {
    setBusyIds(current => new Set(current).add(snack.id));
    try { await mutate(() => snack.has_voted ? api.unvote(token, snack.id) : api.vote(token, snack.id), snack.has_voted ? 'Vote removed.' : 'Your vote has been counted!'); }
    catch { /* Server message is already displayed in notice. */ }
    finally { setBusyIds(current => { const next = new Set(current); next.delete(snack.id); return next; }); }
  }
  return <div className="app-shell">
    <aside className="sidebar"><div className="sidebar-brand"><div className="brand-logo">bpf<span>.</span></div><span className="brand-description">SNACK OVERFLOW</span></div>
      <div className="side-heading">WORKSPACE</div>
      <nav aria-label="Primary navigation"><button onClick={() => setView('pantry')} className={`nav-item ${view === 'pantry' ? 'active' : ''}`}><span>▦</span> Pantry dashboard</button>
        {isAdmin && <button onClick={() => setView('activity')} className={`nav-item ${view === 'activity' ? 'active' : ''}`}><span>◷</span> Activity history</button>}
      </nav>
      <div className="sidebar-bottom"><div className="sidebar-note"><span>✦ PANTRY TIP</span><p>Check what’s running low before you grab your afternoon pick-me-up.</p></div><div className="sidebar-profile"><div className="avatar">{user.name.slice(0, 1)}</div><div><strong>{user.name}</strong><small>{isAdmin ? 'Pantry administrator' : 'Team member'}</small></div><button title="Sign out" aria-label="Sign out" onClick={onLogout}>↪</button></div></div>
    </aside>
    <div className="main-panel"><header className="topbar"><div className="topbar-brand">SNACK <span>OVERFLOW</span></div><div className="topbar-right"><span className="today-mark">✦ Made for snack lovers</span><span className="role-pill">{isAdmin ? '⚙ Admin' : '✦ Member'}</span><button className="topbar-logout" onClick={onLogout}>Sign out ↗</button></div></header>
      <nav className="mobile-nav" aria-label="Mobile navigation">
        <button type="button" className={view === 'pantry' ? 'active' : ''} onClick={() => setView('pantry')}>▦ Pantry</button>
        {isAdmin && <button type="button" className={view === 'activity' ? 'active' : ''} onClick={() => setView('activity')}>◷ Activity</button>}
      </nav>
      <main className="main-content">{view === 'activity' && isAdmin ? <ActivityView token={token}/> : <>
        <div className="welcome-row"><div><p className="eyebrow">WELCOME TO THE PANTRY 👋</p><h1>Hey, {user.name.split(' ')[0]}<span className="period">.</span> Hungry?</h1><p className="muted">Here's what's happening in the office pantry today.</p></div>{isAdmin && <button className="primary add-button" onClick={() => setDialog({ kind: 'add' })}>+ &nbsp; Add a snack</button>}</div>
        <section className="summary-metrics" aria-label="Pantry summary"><Metric caption="Total snacks" value={summary?.total ?? 0} kind="total" tone="blue"/><Metric caption="In stock" value={summary?.stocked ?? 0} kind="box" tone="green"/><Metric caption="Running low" value={summary?.running_low ?? 0} kind="low" tone="amber"/><Metric caption="Out of stock" value={summary?.gone ?? 0} kind="gone" tone="red"/></section>
        <div className="feature-strip"><div className="feature-medal">🏆</div><div><span className="feature-kicker">THE PEOPLE HAVE SPOKEN</span><h2>Snack of the week</h2><p>{summary?.snack_of_the_week ? <>Our current favourite: <strong>{emoji[summary.snack_of_the_week.category]} {summary.snack_of_the_week.name}</strong></> : 'Be the first to vote for a snack this week!'}</p></div><div className="feature-right"><span>★</span><strong>{summary?.snack_of_the_week?.votes_this_week ?? 0}</strong><small>votes this week</small></div></div>
        <section className="pantry-section"><div className="section-heading"><div><p className="eyebrow">THE GOOD STUFF</p><h2>Explore the pantry <span className="heading-count">{snacks?.total ?? '—'}</span></h2><p className="muted">Find a favourite, grab a bite, or vote for the next office champion.</p></div><button className="refresh-button" disabled={loading} onClick={() => void reload()} aria-label="Refresh pantry">↻ &nbsp; Refresh</button></div>
          <div className="filters"><div className="search-wrap"><span aria-hidden="true">⌕</span><input type="search" placeholder="Search for your next snack…" aria-label="Search snacks" value={query} onChange={e => setQuery(e.target.value)} /></div><select aria-label="Filter category" value={category} onChange={e => setCategory(e.target.value as Category | 'all')}><option value="all">All categories</option><option value="sweet">Sweet</option><option value="savoury">Savoury</option><option value="drink">Drinks</option><option value="healthy-ish">Healthy-ish</option></select><select aria-label="Sort snacks" value={sort} onChange={e => setSort(e.target.value)}><option value="name:asc">Name A–Z</option><option value="name:desc">Name Z–A</option><option value="quantity:asc">Stock: low first</option><option value="quantity:desc">Stock: high first</option><option value="votes:desc">Most popular</option></select></div>
          <div className="filter-tabs" role="group" aria-label="Stock status filter">{([['all', 'All snacks'], ['stocked', 'In stock'], ['running_low', 'Running low'], ['gone', 'Out of stock']] as const).map(([key, text]) => <button key={key} type="button" className={filter === key ? 'selected' : ''} onClick={() => setFilter(key)}>{text}{key === 'running_low' && !!summary?.running_low && <span>{summary.running_low}</span>}{key === 'gone' && !!summary?.gone && <span>{summary.gone}</span>}</button>)}</div>
          {loadError ? <div className="state-card error-state">⚠ {loadError}<button className="secondary" onClick={() => void reload()}>Retry</button></div> : loading && !snacks ? <div className="state-card">Fetching fresh snacks…</div> : !snacks?.items.length && !loading ? <div className="state-card"><span className="state-emoji">🍪</span><h3>No snacks found</h3><p>Try changing the filters or searching for something else.</p><button className="secondary" onClick={() => { setFilter('all'); setCategory('all'); setQuery(''); }}>Clear filters</button></div> : <div className={`snack-list ${loading ? 'updating' : ''}`}>{snacks?.items.map(snack => <SnackCard key={snack.id} snack={snack} admin={isAdmin} busy={busyIds.has(snack.id)} onDialog={setDialog} onVote={s => void vote(s)} />)}</div>}
          <div className="pagination"><span>{snacks ? `${snacks.total} snack${snacks.total === 1 ? '' : 's'} found` : 'Loading…'}</span><div><button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1 || loading}>← Previous</button><span>{snacks?.pages ? `${page} / ${snacks.pages}` : '0 / 0'}</span><button onClick={() => setPage(p => p + 1)} disabled={loading || page >= (snacks?.pages ?? 0)}>Next →</button></div></div>
        </section>
      </>}</main><footer className="app-footer"><span>✦ Crafted with care for the hungriest office.</span><span>Bipolar Factory · Full Stack Intern Challenge 2026</span></footer>
    </div>
    {dialog && <SnackDialog key={`${dialog.kind}-${dialog.kind === 'add' ? 'new' : dialog.snack.id}`} dialog={dialog} onClose={() => setDialog(null)} onSave={save} />}
    {notice && <div className={`toast toast-${notice.kind}`} role="status"><span>{notice.kind === 'success' ? '✓' : '⚠'}</span><span>{notice.message}</span><button onClick={() => setNotice(null)} aria-label="Dismiss notification">×</button></div>}
  </div>;
}

export default function App() {
  const [session, setSession] = useState<{ token: string; user: User } | null>(null);
  const [checking, setChecking] = useState(true);
  useEffect(() => {
    const token = sessionStorage.getItem('snack_token');
    if (!token) { setChecking(false); return; }
    let alive = true;
    api.me(token).then(user => { if (alive) setSession({ token, user }); }).catch(() => { sessionStorage.removeItem('snack_token'); }).finally(() => { if (alive) setChecking(false); });
    return () => { alive = false; };
  }, []);
  function login(token: string, user: User) { sessionStorage.setItem('snack_token', token); setSession({ token, user }); }
  function logout() { if (session) void api.logout(session.token).catch(() => {}); sessionStorage.removeItem('snack_token'); setSession(null); }
  if (checking) return <div className="boot-screen">🍿 <span>Opening the pantry…</span></div>;
  return session ? <Dashboard token={session.token} user={session.user} onLogout={logout} /> : <Login onLogin={login} />;
}
