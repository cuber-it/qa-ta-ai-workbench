// QATAKI - Alpine-Root-Komponente
function app() {
  return {
    menuOpen: false,
    // --- Live-Log (Frei 2) ---
    logs: [],
    logFilter: { DEBUG: false, INFO: true, WARNING: true, ERROR: true },
    logOnlyRun: false,
    logHold: false,
    logView: 'log',                 // 'log' | 'usage'
    usage: { entries: [], totals: { calls: 0, input: 0, output: 0, total: 0 }, enabled: true },
    _logES: null,
    get visibleLogs() {
      const f = this.logFilter
      let out = this.logs.filter(e => f[e.level])
      if (this.logOnlyRun && this.activeRunId) out = out.filter(e => e.run === this.activeRunId)
      return out
    },
    settingsOpen: false,
    activeTab: 'llm',
    saved: false,
    settings: {
      provider_type: 'anthropic',
      model: '',
      max_tokens: 1024,
      temperature: 0.7,
      agent_max_tokens: 16384,
      agent_temperature: 0.3,
      agent_max_iterations: 15,
      providers: [],
      key_present: {},
    },
    cost: { by_model: [] },
    budget: {},
    overview: { by_model: [], totals: null },
    pricingStatus: {},
    pending: null,
    kostenPeriod: 'month',
    refreshing: false,
    refreshMsg: '',
    mcp: { servers: {}, primary: null },
    mcpForm: { name: '', url: '', transport: 'http', auth_token: '' },
    mcpMsg: '',
    mcpTools: [],
    mcpToolsFor: null,
    mcpTestMsg: '',
    mcpCall: { tool: '', args: '{}', result: null, running: false },
    connected: false,
    emergency: { active: false },
    _pollTimer: null,

    agentInput: '',
    agentRunning: false,
    dialog: [],
    agentQueue: [],                 // wartende Eingaben, werden nach dem Lauf abgearbeitet
    promptHistory: [],              // gesendete Prompts (Shell-artig, ↑/↓)
    _histIdx: null,
    _histDraft: '',
    toolLog: [],
    artifacts: [],
    allActivityCollapsed: false,
    agentStatus: '',
    agentCosts: null,
    projects: [],
    activeProject: null,
    runs: [],
    activeRunId: '',
    newProjectOpen: false,
    newProject: { name: '', base_url: '', description: '', artifacts_path: '', default_provider: '' },
    artifactsBase: '~/.qataki',
    artifactsTouched: false,
    aboutOpen: false,
    barTokens: 0,
    runModalOpen: false,
    newRunForm: { name: '', url: '', provider: '', headless: true, description: '', artifacts_path: '' },
    runEditOpen: false,
    editRun: { id: '', title: '', url: '', provider: '', model: '', temperature: '', description: '' },
    configDefaults: { project_defaults: {}, run_defaults: { headless: true } },
    skills: [],
    modelsByProvider: {},
    budgetForm: { max_tokens_per_run: null, soft_tokens_per_run: null, max_usd_per_run: null, max_tokens_per_day: null },
    budgetSaved: false,

    // --- Kontext-Editor (System-Prompt + Skills) ---
    ctxView: 'edit',                // 'edit' | 'log'
    ctxItems: [],                   // {type:'prompt'|'skill', key, name, badge, source, when}
    ctxSel: null,                   // ausgewaehlter Eintrag
    ctxLog: [],
    _CTX_BADGE: { default: 'Default', override: 'angepasst', custom: 'eigen' },

    // --- Floating-Kacheln (Default angedockt; loesbar, frei anordenbar) ---
    floaters: {},        // id -> { floating, x, y, w, h, z }
    _floatZ: 100,
    _drag: null,

    // --- Editor-Floater (CodeMirror; Topic-Singleton, generisch) ---
    // Aktuell Topic 'context' (Prompts/Skills); spaeter 'gherkin', 'code' ueber mode + Save-Hook.
    ed: { open: false, topic: '', mode: 'yaml-frontmatter', title: '', kind: '', badge: '', source: '',
          type: '', key: '', hasDefault: false, creating: false, newKey: '', busy: false, msg: '' },
    edCM: null,
    edOrig: '',

    // --- Panel-Bibliothek (Fenster ein-/ausblenden) ---
    PANELS: [
      { id: 'dialog',    title: 'Dialog' },
      { id: 'activity',  title: 'Aktivität' },
      { id: 'artifacts', title: 'Artefakte' },
      { id: 'context',   title: 'Kontext' },
      { id: 'run',       title: 'Lauf' },
      { id: 'free1',     title: 'Frei 1' },
      { id: 'log',       title: 'Log & Verbrauch' },
    ],
    panelsHidden: {},        // id -> true = ausgeblendet
    panelMenuOpen: false,

    init() {
      this._onFloatMove = (e) => this._floatMove(e)
      this._onFloatUp = () => this._floatUp()
      this.loadSettings()
      this.loadConfig()
      this.loadSkills()
      this.loadContext()
      this.loadModels()
      this.pollStatus()
      this._pollTimer = setInterval(() => this.pollStatus(), 4000)
      this.loadProjects().then(() => this._restoreUi())
      this.$watch('settingsOpen', () => this._saveUi())
      this.$watch('activeTab', () => this._saveUi())
      this._startLogStream()
    },

    // ── Floating-Kacheln (pin/unpin, frei anordnen) ──────────────────
    fl(id) {
      if (!this.floaters[id]) this.floaters[id] = { floating: false, x: 90, y: 90, w: 380, h: 300, z: 0 }
      return this.floaters[id]
    },
    isFloating(id) { return !!(this.floaters[id] && this.floaters[id].floating) },
    togglePin(id) {
      const f = this.fl(id)
      const el = this._tileEl(id)
      if (!f.floating) {
        // angedockt -> schweben lassen, an aktueller Bildschirmposition (kein Sprung)
        if (el) {
          const r = el.getBoundingClientRect()
          f.x = Math.max(0, Math.round(r.left)); f.y = Math.max(0, Math.round(r.top))
          f.w = Math.round(r.width); f.h = Math.round(r.height)
        }
        f.floating = true
        this._bringFront(id)
      } else {
        // schwebend -> an gewaehlter Stelle andocken (nur Quads in Stacks; Dialog kehrt heim)
        if (el && el.classList.contains('quad')) {
          const r = el.getBoundingClientRect()
          const t = this._dockTarget(r.left + r.width / 2, r.top + 12)
          if (t) { t.before ? t.stack.insertBefore(el, t.before) : t.stack.appendChild(el) }
        }
        f.floating = false
      }
      this._saveUi()
    },
    floaterStyle(id) {
      const f = this.floaters[id]
      if (!f || !f.floating) return ''
      const z = id === 'editor' ? 9000 : (f.z || 100)   // Editor immer ganz oben
      return `position:fixed;left:${f.x}px;top:${f.y}px;width:${f.w}px;height:${f.h}px;z-index:${z};`
    },
    // Editor: eine Bindung steuert Sichtbarkeit UND Position (kein x-show/:style-Konflikt)
    editorStyle() {
      if (!this.ed.open) return 'display:none'
      const f = this.floaters.editor || { x: 160, y: 120, w: 560, h: 460 }
      return `position:fixed;left:${f.x}px;top:${f.y}px;width:${f.w}px;height:${f.h}px;z-index:9000;`
    },
    _bringFront(id) { this._floatZ++; this.fl(id).z = this._floatZ },
    floaterDown(id, e) {
      if (!this.isFloating(id)) return                                   // angedockt -> nicht draggen
      if (e.target.closest('button, input, textarea, select, .fl-resize')) return
      const f = this.fl(id); this._bringFront(id)
      this._drag = { id, mode: 'move', sx: e.clientX, sy: e.clientY, ox: f.x, oy: f.y }
      e.preventDefault()
      window.addEventListener('mousemove', this._onFloatMove)
      window.addEventListener('mouseup', this._onFloatUp)
    },
    floaterResizeDown(id, e) {
      const f = this.fl(id); this._bringFront(id)
      this._drag = { id, mode: 'resize', sx: e.clientX, sy: e.clientY, ow: f.w, oh: f.h }
      e.preventDefault(); e.stopPropagation()
      window.addEventListener('mousemove', this._onFloatMove)
      window.addEventListener('mouseup', this._onFloatUp)
    },
    _floatMove(e) {
      const d = this._drag; if (!d) return
      const f = this.fl(d.id)
      if (d.mode === 'move') {
        f.x = Math.max(0, d.ox + (e.clientX - d.sx))
        f.y = Math.max(0, d.oy + (e.clientY - d.sy))
      } else {
        f.w = Math.max(240, d.ow + (e.clientX - d.sx))
        f.h = Math.max(140, d.oh + (e.clientY - d.sy))
      }
    },
    _floatUp() {
      window.removeEventListener('mousemove', this._onFloatMove)
      window.removeEventListener('mouseup', this._onFloatUp)
      this._drag = null
      this._saveUi()
    },

    // ── Andocken an frei gewählte Spalten-Position ───────────────────
    _tileEl(id) { return document.querySelector(`[data-fl="${id}"]`) },
    _stacks() { return [...document.querySelectorAll('.pane-col .stack')] },
    // Aus einer Bildschirm-Koordinate Ziel-Spalte (.stack) + Einfüge-Nachbar ermitteln.
    _dockTarget(cx, cy) {
      const stacks = this._stacks()
      if (!stacks.length) return null
      let stack = stacks.find(s => { const r = s.getBoundingClientRect(); return cx >= r.left && cx < r.right })
      if (!stack) {  // ausserhalb aller Spalten -> nächstgelegene nach x-Mitte
        let best = null, bestD = Infinity
        for (const s of stacks) {
          const r = s.getBoundingClientRect(), mid = (r.left + r.right) / 2, d = Math.abs(cx - mid)
          if (d < bestD) { bestD = d; best = s }
        }
        stack = best
      }
      if (!stack) return null
      const docked = [...stack.children].filter(el => el.classList.contains('quad') && !el.classList.contains('floating'))
      let before = null
      for (const el of docked) {
        const r = el.getBoundingClientRect()
        if (cy < r.top + r.height / 2) { before = el; break }
      }
      return { stack, before }
    },
    // Angedocktes Layout erfassen: pro Spalte die Reihenfolge der angedockten Kachel-IDs.
    _captureDock() {
      return this._stacks().map(stack =>
        [...stack.children]
          .filter(el => el.classList.contains('quad') && el.dataset.fl && !this.isFloating(el.dataset.fl))
          .map(el => el.dataset.fl)
      )
    },
    // Gespeichertes Layout nachspielen (DOM-Move in die jeweilige Spalte/Reihenfolge).
    _applyDock(layout) {
      if (!Array.isArray(layout)) return
      const stacks = this._stacks()
      layout.forEach((ids, ci) => {
        const stack = stacks[ci]; if (!stack || !Array.isArray(ids)) return
        ids.forEach(id => { const el = this._tileEl(id); if (el && !this.isFloating(id)) stack.appendChild(el) })
      })
    },
    // Panel-Sichtbarkeit
    isVisible(id) { return !this.panelsHidden[id] },
    togglePanel(id) { this.panelsHidden[id] = !this.panelsHidden[id]; this._saveUi() },

    // ── Editor-Floater (CodeMirror) ──────────────────────────────────
    _edEnsureCM() {
      if (this.edCM || !window.CodeMirror) return
      this.edCM = CodeMirror(this.$refs.edHost, {
        lineNumbers: true, lineWrapping: true, mode: this.ed.mode,
        extraKeys: {
          'Ctrl-S': () => this.edSave(), 'Cmd-S': () => this.edSave(),
          'Ctrl-B': () => this.edWrap('**', '**'), 'Cmd-B': () => this.edWrap('**', '**'),
          'Ctrl-I': () => this.edWrap('*', '*'), 'Cmd-I': () => this.edWrap('*', '*'),
        },
      })
      this.edCM.setSize('100%', '100%')
    },
    _edShow(content, mode) {
      this.ed.open = true
      if (!this.floaters.editor) this.floaters.editor = { floating: true, x: 160, y: 120, w: 560, h: 460, z: 0 }
      const f = this.floaters.editor
      f.x = Math.min(Math.max(0, f.x), Math.max(0, window.innerWidth - 120))
      f.y = Math.min(Math.max(0, f.y), Math.max(0, window.innerHeight - 80))
      f.floating = true
      this._bringFront('editor')
      this.edOrig = content
      this.$nextTick(() => {
        this._edEnsureCM()
        if (this.edCM) {
          this.edCM.setOption('mode', mode || this.ed.mode)
          this.edCM.setValue(content)
          this.edCM.refresh()
          this.edCM.focus()
        }
      })
    },
    get edContent() { return this.edCM ? this.edCM.getValue() : '' },
    get edDirty() { return this.edCM ? (this.edCM.getValue() !== this.edOrig) : false },
    get edCanReset() {
      if (!this.ed.open || this.ed.creating) return false
      return !!this.ed.source && this.ed.source !== 'default'
    },
    get edResetLabel() {
      return (this.ed.type === 'skill' && this.ed.source === 'custom') ? 'Löschen' : 'Zurücksetzen'
    },
    edClose() { this.ed.open = false; this.ed.msg = '' },
    edCancel() { this.edClose() },   // Abbrechen = verwerfen und schliessen
    edWrap(before, after) {
      const cm = this.edCM; if (!cm) return
      cm.focus()
      const sel = cm.getSelection()
      cm.replaceSelection(before + sel + after)
      if (!sel) { const c = cm.getCursor(); cm.setCursor({ line: c.line, ch: c.ch - after.length }) }
    },
    edPrefix(prefix) {
      const cm = this.edCM; if (!cm) return
      cm.focus()
      const from = cm.getCursor('from'), to = cm.getCursor('to')
      for (let l = from.line; l <= to.line; l++) cm.replaceRange(prefix, { line: l, ch: 0 })
    },
    async edSave() {
      if (this.ed.busy) return
      const creating = this.ed.creating
      const type = this.ed.type
      const key = (creating ? this.ed.newKey : (this.ed.key || '')).trim()
      const content = this.edContent
      if (!key) { this.ed.msg = 'Name fehlt'; return }
      if (!content.trim()) { this.ed.msg = 'Inhalt fehlt'; return }
      this.ed.busy = true; this.ed.msg = ''
      const url = (type === 'prompt' ? '/api/context/prompt/' : '/api/context/skill/') + encodeURIComponent(key)
      try {
        const r = await fetch(url, {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content }),
        })
        const d = await r.json()
        if (r.ok) {
          this.edOrig = content
          this.ed.creating = false
          if (type === 'skill' && d.key) this.ed.key = d.key
          await this.loadContext()
          const it = this.ctxItems.find(x => x.type === type && x.key === this.ed.key)
          if (it) { this.ed.source = it.source; this.ed.badge = it.badge; this.ed.title = it.name; this.ctxSel = it }
          this.ed.msg = 'gespeichert ✓'
          setTimeout(() => { this.ed.msg = '' }, 2000)
        } else { this.ed.msg = d.detail || 'Fehler' }
      } catch (e) { this.ed.msg = 'Fehler beim Speichern' }
      this.ed.busy = false
    },
    async edReset() {
      if (this.ed.busy || !this.edCanReset) return
      const { type, key, source, title } = this.ed
      const isCustom = type === 'skill' && source === 'custom'
      if (!confirm(`„${title}" wirklich ${isCustom ? 'löschen' : 'auf den Default zurücksetzen'}?`)) return
      this.ed.busy = true; this.ed.msg = ''
      const url = (type === 'prompt' ? '/api/context/prompt/' : '/api/context/skill/') + encodeURIComponent(key)
      try {
        const r = await fetch(url, { method: 'DELETE' })
        const d = await r.json()
        if (r.ok) {
          await this.loadContext()
          if (isCustom) { this.edClose(); this.ctxSel = null }
          else {
            const it = this.ctxItems.find(x => x.type === type && x.key === key)
            if (it) await this.selectCtx(it)
            else this.edClose()
          }
        } else { this.ed.msg = d.detail || 'Fehler'; this.ed.busy = false; return }
      } catch (e) { this.ed.msg = 'Fehler'; this.ed.busy = false; return }
      this.ed.busy = false
    },

    async loadConfig() {
      try {
        const r = await fetch('/api/config')
        if (r.ok) this.configDefaults = await r.json()
      } catch (e) { /* eingebaute Defaults bleiben */ }
    },

    async loadSkills() {
      try {
        const r = await fetch('/api/skills')
        if (r.ok) this.skills = (await r.json()).skills || []
      } catch (e) { /* Skills sind unkritisch */ }
    },

    // ── Kontext-Editor ───────────────────────────────────────────────
    async loadContext() {
      try {
        const r = await fetch('/api/context')
        if (!r.ok) return
        const d = await r.json()
        const items = []
        for (const p of (d.prompts || [])) {
          const src = p.overridden ? 'override' : 'default'
          items.push({ type: 'prompt', key: p.name, name: 'System-Prompt',
                       source: src, badge: p.overridden ? 'angepasst' : 'Default' })
        }
        for (const s of (d.skills || [])) {
          items.push({ type: 'skill', key: s.key, name: s.name, when: s.when_to_use,
                       source: s.source, badge: this._CTX_BADGE[s.source] || s.source })
        }
        this.ctxItems = items
      } catch (e) { /* Editor bleibt leer */ }
    },

    setCtxView(v) {
      this.ctxView = v
      if (v === 'log') this.loadCtxLog()
    },

    async loadCtxLog() {
      try {
        const r = await fetch('/api/context/changelog?limit=200')
        if (r.ok) this.ctxLog = (await r.json()).entries || []
      } catch (e) { /* unkritisch */ }
    },

    async selectCtx(item) {
      this.ctxSel = item
      const url = item.type === 'prompt'
        ? '/api/context/prompt/' + encodeURIComponent(item.key)
        : '/api/context/skill/' + encodeURIComponent(item.key)
      try {
        const r = await fetch(url)
        if (!r.ok) return
        const d = await r.json()
        this.ed.topic = 'context'
        this.ed.type = item.type
        this.ed.kind = item.type === 'prompt' ? 'System-Prompt' : 'Skill'
        this.ed.key = item.key
        this.ed.title = item.name
        this.ed.source = item.source
        this.ed.badge = item.badge
        this.ed.hasDefault = item.type === 'skill' ? !!d.has_default : false
        this.ed.creating = false
        this.ed.newKey = ''
        this.ed.mode = item.type === 'prompt' ? 'markdown' : 'yaml-frontmatter'
        this.ed.msg = ''
        this._edShow(d.content || '', this.ed.mode)
      } catch (e) { /* still */ }
    },

    newSkill() {
      this.ctxSel = null
      this.ed.topic = 'context'
      this.ed.type = 'skill'
      this.ed.kind = 'Skill'
      this.ed.key = ''
      this.ed.title = 'Neuer Skill'
      this.ed.source = 'custom'
      this.ed.badge = 'eigen'
      this.ed.hasDefault = false
      this.ed.creating = true
      this.ed.newKey = ''
      this.ed.mode = 'yaml-frontmatter'
      this.ed.msg = ''
      this._edShow('---\nname: \nwhen_to_use: \n---\n\n', 'yaml-frontmatter')
    },

    async loadModels() {
      try {
        const r = await fetch('/api/models')
        if (r.ok) this.modelsByProvider = (await r.json()).models || {}
      } catch (e) { /* Modelle sind unkritisch */ }
    },

    // Modelle zum gewaehlten Provider (leer = Projekt-Default-Provider)
    modelsFor(provider) {
      const eff = provider || (this.activeProject && this.activeProject.default_provider) || ''
      return this.modelsByProvider[eff] || []
    },

    async copy(text) {
      const t = text == null ? '' : String(text)
      try {
        if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(t); return }
      } catch (e) { /* Fallback unten */ }
      try {                                   // Fallback fuer unsichere Kontexte (http im LAN)
        const ta = document.createElement('textarea')
        ta.value = t; ta.style.position = 'fixed'; ta.style.opacity = '0'
        document.body.appendChild(ta); ta.select()
        document.execCommand('copy'); document.body.removeChild(ta)
      } catch (e) { console.error('copy', e) }
    },

    // Aktives Modell des offenen Runs (fuer die Anzeige oben rechts)
    get activeModelLabel() {
      const r = this.runs.find(x => x.id === this.activeRunId)
      if (!r) return ''
      if (r.model) return r.model
      if (r.provider) return r.provider + ' · Standard'
      return ''
    },

    async pollStatus() {
      try {
        const r = await fetch('/api/emergency-status', { cache: 'no-store' })
        if (r.ok) { this.connected = true; this.emergency = await r.json() }
        else { this.connected = false }
      } catch (e) { this.connected = false }
      this.loadBarStats()
    },

    async loadBarStats() {
      try {
        const r = await fetch('/api/cost/overview?period=all')
        if (r.ok) { const o = await r.json(); this.barTokens = (o.totals && o.totals.total_tokens) || 0 }
      } catch (e) { /* Bar-Statistik ist unkritisch */ }
    },

    async triggerEmergency() {
      try { await fetch('/api/emergency-stop', { method: 'POST' }) }
      catch (e) { console.error('stop', e) }
      await this.pollStatus()
    },

    confirmResume() {
      if (confirm('NOTAUS aufheben und LLM-Calls wieder zulassen?')) this.resumeEmergency()
    },

    async resumeEmergency() {
      try { await fetch('/api/emergency-resume', { method: 'POST' }) }
      catch (e) { console.error('resume', e) }
      await this.pollStatus()
    },

    async openSettings() {
      this.menuOpen = false
      this.saved = false
      await this.loadSettings()
      await this.loadCost()
      this.settingsOpen = true
    },

    async loadSettings() {
      try {
        const r = await fetch('/api/settings')
        if (r.ok) this.settings = await r.json()
      } catch (e) { console.error('settings', e) }
    },

    async loadCost() {
      try {
        const r = await fetch('/api/cost')
        if (r.ok) this.cost = await r.json()
      } catch (e) { console.error('cost', e) }
    },

    async loadKosten() {
      await Promise.all([this.loadBudget(), this.loadOverview(), this.loadPricing()])
    },

    async loadBudget() {
      try {
        const r = await fetch('/api/budget')
        if (r.ok) {
          this.budget = await r.json()
          const l = this.budget.limits || {}
          this.budgetForm = {
            max_tokens_per_run: l.hard_tokens_per_run,
            soft_tokens_per_run: l.soft_tokens_per_run,
            max_usd_per_run: l.hard_usd_per_run,
            max_tokens_per_day: l.hard_tokens_per_day,
          }
        }
      } catch (e) { console.error('budget', e) }
    },

    async saveBudget() {
      this.budgetSaved = false
      try {
        const r = await fetch('/api/budget', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            max_tokens_per_run: Number(this.budgetForm.max_tokens_per_run) || null,
            soft_tokens_per_run: Number(this.budgetForm.soft_tokens_per_run) || null,
            max_usd_per_run: Number(this.budgetForm.max_usd_per_run) || null,
            max_tokens_per_day: Number(this.budgetForm.max_tokens_per_day) || null,
          }),
        })
        if (r.ok) { this.budget = await r.json(); this.budgetSaved = true; setTimeout(() => { this.budgetSaved = false }, 2000) }
      } catch (e) { console.error('saveBudget', e) }
    },

    async loadOverview() {
      try {
        const r = await fetch('/api/cost/overview?period=' + this.kostenPeriod)
        if (r.ok) this.overview = await r.json()
      } catch (e) { console.error('overview', e) }
    },

    async loadPricing() {
      try {
        const s = await fetch('/api/pricing/status'); if (s.ok) this.pricingStatus = await s.json()
        const p = await fetch('/api/pricing/pending'); if (p.ok) this.pending = (await p.json()).pending
      } catch (e) { console.error('pricing', e) }
    },

    async refreshPricing() {
      this.refreshing = true; this.refreshMsg = ''
      try {
        const r = await fetch('/api/pricing/refresh', { method: 'POST' })
        const d = await r.json()
        if (r.ok) {
          const errs = (d.errors || []).length ? ` · Fehler: ${d.errors.length}` : ''
          this.refreshMsg = `Geprüft: ${(d.checked || []).join(', ') || '—'} · ${(d.changes || []).length} Änderung(en)${errs}`
        } else {
          this.refreshMsg = d.detail || 'Fehler beim Aktualisieren'
        }
      } catch (e) { this.refreshMsg = 'Fehler beim Aktualisieren' }
      this.refreshing = false
      await this.loadPricing()
    },

    async applyPricing() {
      try { await fetch('/api/pricing/apply', { method: 'POST' }) } catch (e) { console.error('apply', e) }
      await this.loadPricing()
    },

    async rejectPricing() {
      try { await fetch('/api/pricing/reject', { method: 'POST' }) } catch (e) { console.error('reject', e) }
      await this.loadPricing()
    },

    async loadMcp() {
      try { const r = await fetch('/api/mcp/servers'); if (r.ok) this.mcp = await r.json() }
      catch (e) { console.error('mcp', e) }
    },

    async addMcpServer() {
      this.mcpMsg = ''
      try {
        const r = await fetch('/api/mcp/servers', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: this.mcpForm.name, url: this.mcpForm.url,
            transport: this.mcpForm.transport, auth_token: this.mcpForm.auth_token || null,
          }),
        })
        const d = await r.json()
        if (r.ok) { this.mcp = d; this.mcpForm = { name: '', url: '', transport: 'http', auth_token: '' } }
        else this.mcpMsg = d.detail || 'Fehler'
      } catch (e) { this.mcpMsg = 'Fehler beim Hinzufügen' }
    },

    async removeMcpServer(name) {
      try { const r = await fetch('/api/mcp/servers/' + encodeURIComponent(name), { method: 'DELETE' }); if (r.ok) this.mcp = await r.json() } catch (e) {}
      if (this.mcpToolsFor === name) { this.mcpToolsFor = null; this.mcpTools = []; this.mcpCall.tool = '' }
    },

    async setMcpPrimary(name) {
      try {
        const r = await fetch('/api/mcp/primary', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) })
        if (r.ok) this.mcp = await r.json()
      } catch (e) {}
    },

    async testMcpServer(name) {
      this.mcpTestMsg = 'teste ' + name + ' …'
      try {
        const r = await fetch('/api/mcp/servers/' + encodeURIComponent(name) + '/test', { method: 'POST' })
        const d = await r.json()
        this.mcpTestMsg = r.ok ? `${name}: ok, ${d.tool_count} Tool(s)` : `${name}: ${d.detail || 'Fehler'}`
      } catch (e) { this.mcpTestMsg = name + ': Fehler' }
    },

    async loadMcpTools(name) {
      this.mcpToolsFor = name; this.mcpTools = []; this.mcpCall.tool = ''; this.mcpCall.result = null
      try {
        const r = await fetch('/api/mcp/servers/' + encodeURIComponent(name) + '/tools')
        const d = await r.json()
        if (r.ok) this.mcpTools = d.tools || []
        else this.mcpTestMsg = `${name}: ${d.detail || 'Fehler'}`
      } catch (e) { this.mcpTestMsg = name + ': Fehler beim Laden' }
    },

    pickMcpTool(t) {
      this.mcpCall.tool = t.name; this.mcpCall.result = null
      const props = (t.input_schema && t.input_schema.properties) || {}
      const tmpl = {}
      for (const k in props) tmpl[k] = props[k].default !== undefined ? props[k].default : ''
      this.mcpCall.args = JSON.stringify(tmpl, null, 2)
    },

    async runMcpTool(name) {
      this.mcpCall.running = true; this.mcpCall.result = null
      let args = {}
      try { args = this.mcpCall.args.trim() ? JSON.parse(this.mcpCall.args) : {} }
      catch (e) { this.mcpCall.result = 'Ungültiges JSON in den Argumenten'; this.mcpCall.running = false; return }
      try {
        const r = await fetch('/api/mcp/servers/' + encodeURIComponent(name) + '/call', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tool: this.mcpCall.tool, arguments: args }),
        })
        const d = await r.json()
        this.mcpCall.result = r.ok ? (d.content || JSON.stringify(d, null, 2)) : (d.detail || 'Fehler')
      } catch (e) { this.mcpCall.result = 'Fehler beim Ausführen' }
      this.mcpCall.running = false
    },

    async saveSettings() {
      this.saved = false
      const body = {
        provider_type: this.settings.provider_type,
        model: this.settings.model || '',
        max_tokens: Number(this.settings.max_tokens) || 1024,
        temperature: Number(this.settings.temperature),
        agent_max_tokens: Number(this.settings.agent_max_tokens) || 16384,
        agent_temperature: Number(this.settings.agent_temperature),
        agent_max_iterations: Number(this.settings.agent_max_iterations) || 15,
      }
      try {
        const r = await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        if (r.ok) { this.saved = true; setTimeout(() => { this.saved = false }, 2000) }
      } catch (e) { console.error('save', e) }
    },

    sendAgent() {
      const text = this.agentInput.trim()
      if (!text || !this.activeRunId) return
      this.agentInput = ''
      this._pushHistory(text)
      // Nachricht sofort sichtbar; laeuft schon einer -> einreihen.
      const msg = { role: 'user', text, queued: this.agentRunning }
      this.dialog.push(msg)
      this._scrollChat()
      if (this.agentRunning) { this.agentQueue.push(msg); return }
      this._runAgent(text)
    },

    async _runAgent(text) {
      this.agentRunning = true
      this.agentStatus = 'läuft…'
      this.agentCosts = null
      this._agentStopped = false
      this._agentAbort = new AbortController()
      this._scrollChat()
      try {
        const r = await fetch('/api/agent/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: this._agentAbort.signal,
          body: JSON.stringify({
            session_id: this.activeRunId || '',
            project_id: this.activeProject.id,
            text,
          }),
        })
        if (!r.ok || !r.body) { this.agentStatus = 'Fehler ' + r.status; return }
        const reader = r.body.getReader()
        const dec = new TextDecoder()
        let buf = ''
        while (true) {
          const { value, done } = await reader.read()
          if (done) break
          buf += dec.decode(value, { stream: true })
          let idx
          while ((idx = buf.indexOf('\n\n')) >= 0) {
            const chunk = buf.slice(0, idx); buf = buf.slice(idx + 2)
            const line = chunk.split('\n').find(l => l.startsWith('data: '))
            if (!line) continue
            let ev; try { ev = JSON.parse(line.slice(6)) } catch (e) { continue }
            this._onAgentEvent(ev)
          }
        }
      } catch (e) {
        this.agentStatus = (this._agentStopped || e.name === 'AbortError') ? 'gestoppt' : 'Verbindungsfehler'
      } finally {
        this._agentAbort = null
        this.agentRunning = false
        this.loadRuns()
        this.loadArtifacts()
        this._drainQueue()
      }
    },

    _drainQueue() {
      if (!this.agentQueue.length) return
      const msg = this.agentQueue.shift()
      msg.queued = false
      this._runAgent(msg.text)
    },

    removeQueued(msg) {
      // Einzelnen wartenden Eintrag aus der Warteschlange nehmen.
      const i = this.agentQueue.indexOf(msg)
      if (i >= 0) { this.agentQueue.splice(i, 1); msg.queued = false; msg.cancelled = true }
    },

    stopAgent() {
      // Bricht NUR den laufenden Schritt ab. Die Warteschlange laeuft danach
      // weiter (ueber den finally-Drain in _runAgent).
      if (!this.agentRunning) return
      this._agentStopped = true
      if (this._agentAbort) this._agentAbort.abort()
      this.agentRunning = false
      const skipped = this.agentQueue.length > 0
      this.agentStatus = skipped ? 'übersprungen – Warteschlange läuft weiter' : 'gestoppt'
      this.dialog.push({ role: 'divider', text: skipped ? 'übersprungen' : 'unterbrochen' })
      this._scrollChat()
    },

    // ── Prompt-History (↑/↓ wie in der Shell) ────────────────────────
    _pushHistory(text) {
      if (this.promptHistory[this.promptHistory.length - 1] !== text) {
        this.promptHistory.push(text)
        if (this.promptHistory.length > 200) this.promptHistory.shift()
      }
      this._histIdx = null; this._histDraft = ''
    },
    historyPrev(e) {
      const ta = e.target, v = ta.value
      if (v.lastIndexOf('\n', ta.selectionStart - 1) !== -1) return   // nicht in erster Zeile -> normal
      if (!this.promptHistory.length) return
      e.preventDefault()
      if (this._histIdx === null) { this._histDraft = this.agentInput; this._histIdx = this.promptHistory.length }
      this._histIdx = Math.max(0, this._histIdx - 1)
      this.agentInput = this.promptHistory[this._histIdx]
      this.$nextTick(() => { ta.selectionStart = ta.selectionEnd = ta.value.length })
    },
    historyNext(e) {
      const ta = e.target, v = ta.value
      if (this._histIdx === null) return                              // nicht im History-Modus
      if (v.indexOf('\n', ta.selectionStart) !== -1) return           // nicht in letzter Zeile -> normal
      e.preventDefault()
      this._histIdx++
      if (this._histIdx >= this.promptHistory.length) {
        this._histIdx = null
        this.agentInput = this._histDraft
      } else {
        this.agentInput = this.promptHistory[this._histIdx]
      }
      this.$nextTick(() => { ta.selectionStart = ta.selectionEnd = ta.value.length })
    },

    _onAgentEvent(ev) {
      switch (ev.type) {
        case 'start':
          this.activeRunId = ev.session_id; break
        case 'assistant':
          this.dialog.push({ role: 'assistant', text: ev.text }); break
        case 'tool_use':
          this.agentStatus = ev.name + ' …'
          this.toolLog.push({ id: ev.id, name: ev.name,
            input: this._fmtInput(ev.input), result: null, is_error: false,
            collapsed: this.allActivityCollapsed }); break
        case 'tool_result': {
          const e = [...this.toolLog].reverse().find(x => x.id === ev.tool_use_id && x.result === null)
          if (e) { e.result = String(ev.content); e.is_error = !!ev.is_error }
          else this.toolLog.push({ id: ev.tool_use_id, name: '', input: '',
            result: String(ev.content), is_error: !!ev.is_error })
          break
        }
        case 'final':
          this.agentStatus = 'fertig'; break
        case 'note':
          this.dialog.push({ role: 'note', text: ev.message }); break
        case 'error':
          this.dialog.push({ role: 'assistant', text: '⚠ ' + ev.message })
          this.agentStatus = ev.message; break
        case 'done':
          this.agentCosts = ev.costs || null
          if (ev.stopped) this.agentStatus = 'gestoppt: ' + ev.stopped
          else if (!this.agentStatus || this.agentStatus === 'läuft…') this.agentStatus = 'fertig'
          break
      }
      this._scrollChat()
    },

    _scrollChat() {
      this.$nextTick(() => { const el = this.$refs.chat; if (el) el.scrollTop = el.scrollHeight })
    },

    // --- Live-Log (Frei 2) ---
    _startLogStream() {
      if (this._logES) return
      const es = new EventSource('/api/logs/stream?backfill=200')
      es.onmessage = (ev) => {
        let e
        try { e = JSON.parse(ev.data) } catch (_) { return }
        this.logs.push(e)
        if (this.logs.length > 1000) this.logs.splice(0, this.logs.length - 1000)
        if (!this.logHold) this._scrollLog()
        // Realtime-Usage: jeder LLM-Call erzeugt genau eine "LLM-Antwort"-Zeile.
        if (this.logView === 'usage' && e.name === 'uc_agent_core.loop'
            && typeof e.msg === 'string' && e.msg.startsWith('LLM-Antwort')) {
          this.loadUsage()
        }
      }
      // EventSource reconnectet bei Fehler automatisch
      this._logES = es
    },
    _scrollLog() {
      this.$nextTick(() => { const el = this.$refs.logBody; if (el) el.scrollTop = el.scrollHeight })
    },
    toggleLogLevel(lv) { this.logFilter[lv] = !this.logFilter[lv] },
    toggleLogRun() { this.logOnlyRun = !this.logOnlyRun; if (!this.logHold) this._scrollLog() },
    toggleLogHold() { this.logHold = !this.logHold; if (!this.logHold) this._scrollLog() },
    logToTop() { this.logHold = true; const el = this.$refs.logBody; if (el) el.scrollTop = 0 },
    logToBottom() { this.logHold = false; const el = this.$refs.logBody; if (el) el.scrollTop = el.scrollHeight },
    logShort(lv) { return { DEBUG: 'DBG', INFO: 'INF', WARNING: 'WRN', ERROR: 'ERR' }[lv] || lv },
    setLogView(v) {
      this.logView = v
      if (v === 'usage') this.loadUsage()
    },
    async loadUsage() {
      try {
        const r = await fetch('/api/usage?limit=500')
        if (r.ok) this.usage = await r.json()
      } catch (_) { /* still bleiben */ }
    },
    fmt(n) { return (n || 0).toLocaleString('de-DE') },

    // ── Projekte / Runs ──────────────────────────────────────────────
    async loadProjects() {
      try { const r = await fetch('/api/projects'); if (r.ok) this.projects = (await r.json()).projects || [] }
      catch (e) { console.error('projects', e) }
    },

    createProject() {
      const d = this.configDefaults.project_defaults || {}
      this.artifactsBase = (d.artifacts_base || '~/.qataki').replace(/\/+$/, '')
      this.artifactsTouched = false
      this.newProject = {
        name: '',
        base_url: d.base_url || '',
        description: d.description || '',
        artifacts_path: this.artifactsBase,
        default_provider: d.default_provider || '',
      }
      this.newProjectOpen = true
    },

    onProjectName() {
      if (this.artifactsTouched) return
      const n = this.newProject.name.trim()
      this.newProject.artifacts_path = n ? this.artifactsBase + '/' + n : this.artifactsBase
    },

    openAbout() {
      this.menuOpen = false
      this.aboutOpen = true
    },

    loadProject() {
      // Platzhalter: Import aus anderen Quellen / noch nicht in der DB. Folgt spaeter.
      this.menuOpen = false
    },

    async submitNewProject() {
      const name = this.newProject.name.trim()
      if (!name) return
      try {
        const r = await fetch('/api/projects', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...this.newProject, name }),
        })
        if (r.ok) { const p = await r.json(); this.newProjectOpen = false; await this.loadProjects(); this.selectProject(p) }
      } catch (e) { console.error('createProject', e) }
    },

    selectProject(p) {
      this.activeProject = p
      this.clearRun()
      this.loadRuns()
      this._saveUi()
    },

    async deleteProject(p) {
      if (!confirm(`Projekt "${p.name}" samt Runs löschen?`)) return
      try { await fetch('/api/projects/' + encodeURIComponent(p.id), { method: 'DELETE' }) }
      catch (e) { console.error('deleteProject', e) }
      await this.loadProjects()
      if (this.activeProject && this.activeProject.id === p.id) {
        this.activeProject = null; this.runs = []; this.newRun()
        this._saveUi()
      }
    },

    async renameProject(p) {
      const name = prompt('Neuer Projektname:', p.name)
      if (name === null) return
      const v = name.trim()
      if (!v || v === p.name) return
      try {
        await fetch('/api/projects/' + encodeURIComponent(p.id) + '/rename', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: v }),
        })
        await this.loadProjects()
        if (this.activeProject && this.activeProject.id === p.id) this.activeProject.name = v
      } catch (e) { console.error('renameProject', e) }
    },

    async loadRuns() {
      if (!this.activeProject) { this.runs = []; return }
      try {
        const r = await fetch('/api/agent/sessions?project_id=' + encodeURIComponent(this.activeProject.id))
        if (r.ok) this.runs = (await r.json()).sessions || []
      } catch (e) { console.error('runs', e) }
    },

    clearRun() {
      this.activeRunId = ''
      this.dialog = []; this.toolLog = []; this.artifacts = []
      this.agentCosts = null; this.agentStatus = ''
      this.promptHistory = []; this._histIdx = null; this._histDraft = ''
    },

    toggleAllActivity() {
      this.allActivityCollapsed = !this.allActivityCollapsed
      this.toolLog.forEach(t => { t.collapsed = this.allActivityCollapsed })
    },

    newRun() {
      if (!this.activeProject) return
      const p = this.activeProject
      const n = new Date(), z = x => String(x).padStart(2, '0')
      const stamp = `${n.getFullYear()}-${z(n.getMonth() + 1)}-${z(n.getDate())} ${z(n.getHours())}:${z(n.getMinutes())}`
      this.newRunForm = {
        name: stamp,
        url: p.base_url || '',
        provider: p.default_provider || '',
        headless: this.configDefaults.run_defaults?.headless ?? true,
        description: '',
        artifacts_path: p.artifacts_path || '',
        model: '',
        temperature: '',
      }
      this.runModalOpen = true
    },

    async submitNewRun() {
      if (!this.activeProject) return
      try {
        const r = await fetch('/api/agent/runs', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ project_id: this.activeProject.id, ...this.newRunForm }),
        })
        if (r.ok) {
          const run = await r.json()
          this.runModalOpen = false
          this.clearRun()
          this.activeRunId = run.id
          await this.loadRuns()
          this._saveUi()
        }
      } catch (e) { console.error('createRun', e) }
    },

    async openRun(r) {
      this.clearRun()
      this.activeRunId = r.id
      this._saveUi()
      try {
        const res = await fetch('/api/agent/sessions/' + encodeURIComponent(r.id))
        if (res.ok) this._rehydrate((await res.json()).events || [])
      } catch (e) { console.error('openRun', e) }
      this.loadArtifacts()
    },

    _saveUi() {
      try {
        localStorage.setItem('qataki.ui', JSON.stringify({
          projectId: this.activeProject ? this.activeProject.id : '',
          runId: this.activeRunId || '',
          settingsOpen: !!this.settingsOpen,
          activeTab: this.activeTab || 'llm',
          floaters: this.floaters,
          dock: this._captureDock(),
          panelsHidden: this.panelsHidden,
        }))
      } catch (e) {}
    },

    async _restoreUi() {
      let ui
      try { ui = JSON.parse(localStorage.getItem('qataki.ui') || '{}') } catch (e) { return }
      if (!ui) return
      if (ui.floaters) {
        this.floaters = ui.floaters
        let mx = 100
        for (const k in ui.floaters) { const z = ui.floaters[k] && ui.floaters[k].z; if (z > mx) mx = z }
        this._floatZ = mx
      }
      if (ui.dock) this._applyDock(ui.dock)
      if (ui.panelsHidden) this.panelsHidden = ui.panelsHidden
      if (ui.activeTab) this.activeTab = ui.activeTab
      if (ui.settingsOpen) this.settingsOpen = true
      if (!ui.projectId) return
      const p = this.projects.find(x => x.id === ui.projectId)
      if (!p) return
      this.activeProject = p
      await this.loadRuns()
      if (ui.runId) {
        const r = this.runs.find(x => x.id === ui.runId)
        if (r) await this.openRun(r)
      }
    },

    async rerunRun(r) {
      try {
        const res = await fetch('/api/agent/sessions/' + encodeURIComponent(r.id) + '/rerun', { method: 'POST' })
        if (!res.ok) { console.error('rerun', res.status); return }
        const data = await res.json()
        await this.loadRuns()
        await this.openRun({ id: data.id })
        this.agentInput = data.task || ''   // vorbefuellen, Nutzer sendet selbst
      } catch (e) { console.error('rerun', e) }
    },

    openRunEdit(r) {
      this.editRun = {
        id: r.id,
        title: r.title || '',
        url: r.url || '',
        provider: r.provider || '',
        model: r.model || '',
        temperature: r.temperature || '',
        description: r.description || '',
      }
      this.runEditOpen = true
    },

    async submitRunEdit() {
      const e = this.editRun
      try {
        await fetch('/api/agent/sessions/' + encodeURIComponent(e.id) + '/edit', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: e.title, url: e.url, provider: e.provider, model: e.model, temperature: e.temperature, description: e.description }),
        })
        this.runEditOpen = false
        await this.loadRuns()
      } catch (err) { console.error('submitRunEdit', err) }
    },

    async deleteRun(r) {
      if (!confirm(`Run "${this.runLabel(r)}" löschen?`)) return
      try { await fetch('/api/agent/sessions/' + encodeURIComponent(r.id), { method: 'DELETE' }) }
      catch (e) { console.error('deleteRun', e) }
      if (this.activeRunId === r.id) this.clearRun()
      await this.loadRuns()
    },

    async loadArtifacts() {
      if (!this.activeRunId) { this.artifacts = []; return }
      try {
        const r = await fetch('/api/agent/sessions/' + encodeURIComponent(this.activeRunId) + '/artifacts')
        if (r.ok) this.artifacts = (await r.json()).artifacts || []
      } catch (e) { /* Artefakte sind unkritisch */ }
    },

    openArtifact(a) {
      if (!this.activeRunId) return
      const enc = a.name.split('/').map(encodeURIComponent).join('/')
      window.open('/api/agent/sessions/' + encodeURIComponent(this.activeRunId) + '/artifacts/' + enc, '_blank')
    },

    fmtSize(n) {
      n = n || 0
      if (n < 1024) return n + ' B'
      if (n < 1048576) return (n / 1024).toFixed(1) + ' KB'
      return (n / 1048576).toFixed(1) + ' MB'
    },

    _assistantText(content) {
      if (typeof content === 'string') return content
      if (Array.isArray(content)) return content.filter(b => b.type === 'text').map(b => b.text).join('')
      return ''
    },

    _fmtInput(input) {
      if (input == null) return ''
      let s
      try { s = JSON.stringify(input) } catch (e) { s = String(input) }
      return s === '{}' ? '' : s
    },

    _rehydrate(events) {
      this.promptHistory = []; this._histIdx = null; this._histDraft = ''
      for (const e of events) {
        if (e.type === 'user') {
          this.dialog.push({ role: 'user', text: e.text })
          if (this.promptHistory[this.promptHistory.length - 1] !== e.text) this.promptHistory.push(e.text)
        }
        else if (e.type === 'assistant') { const t = this._assistantText(e.content); if (t) this.dialog.push({ role: 'assistant', text: t }) }
        else if (e.type === 'tool_use') this.toolLog.push({ id: e.id, name: e.name, input: this._fmtInput(e.input), result: null, is_error: false, collapsed: this.allActivityCollapsed })
        else if (e.type === 'tool_result') {
          const x = [...this.toolLog].reverse().find(t => t.id === e.tool_use_id && t.result === null)
          if (x) { x.result = String(e.content); x.is_error = !!e.is_error }
          else this.toolLog.push({ id: e.tool_use_id, name: '', input: '', result: String(e.content), is_error: !!e.is_error })
        }
        else if (e.type === 'note') this.dialog.push({ role: 'note', text: 'Validierung: ' + (e.detail || e.reason || '') })
        else if (e.type === 'error') this.dialog.push({ role: 'note', text: '⚠ ' + (e.reason || e.message || 'Fehler') })
      }
      this._scrollChat()
    },

    runLabel(r) {
      if (r.title) return r.title
      if (r.created_at) return 'Run · ' + new Date(r.created_at).toLocaleString()
      return 'Run ' + r.id.slice(0, 6)
    },

    get costLine() {
      const c = this.agentCosts; if (!c) return ''
      const usd = (c.cost_usd != null) ? ('$' + Number(c.cost_usd).toFixed(4)) : ''
      return `${c.llm_calls || 0} Calls · ${c.tokens || 0} Tokens · ${usd}`
    },

    get keyOk() {
      const kp = this.settings.key_present || {}
      return !!kp[this.settings.provider_type]
    },

    get statusClass() {
      if (!this.connected || this.emergency.active) return 'conn-off'
      if (!this.keyOk) return 'conn-warn'
      return 'conn-on'
    },

    get statusTitle() {
      if (!this.connected) return 'Keine Verbindung zum Server'
      if (this.emergency.active) return 'NOTAUS aktiv'
      if (!this.keyOk) return 'Kein API-Key für ' + this.settings.provider_type
      return 'Bereit · ' + this.settings.provider_type + '/' + (this.settings.model || '?')
    },

    get barStatusText() {
      const p = this.settings.provider_type || '?'
      const m = this.settings.model || 'Default'
      const t = (this.barTokens || 0).toLocaleString('de-DE')
      return p + ' / ' + m + ' · ' + t + ' Token'
    },
  }
}
