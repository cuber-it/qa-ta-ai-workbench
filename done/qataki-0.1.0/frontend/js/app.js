// QATAKI - Alpine-Root-Komponente
function app() {
  return {
    menuOpen: false,
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

    init() {
      this.loadSettings()
      this.loadConfig()
      this.loadSkills()
      this.loadModels()
      this.pollStatus()
      this._pollTimer = setInterval(() => this.pollStatus(), 4000)
      this.loadProjects()
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

    async sendAgent() {
      const text = this.agentInput.trim()
      if (!text || this.agentRunning || !this.activeRunId) return
      this.dialog.push({ role: 'user', text })
      this.agentInput = ''
      this.agentRunning = true
      this.agentStatus = 'läuft…'
      this.agentCosts = null
      this._scrollChat()
      try {
        const r = await fetch('/api/agent/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: this.activeRunId || '',
            project_id: this.activeProject.id,
            text,
          }),
        })
        if (!r.ok || !r.body) { this.agentStatus = 'Fehler ' + r.status; this.agentRunning = false; return }
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
        this.agentStatus = 'Verbindungsfehler'
      }
      this.agentRunning = false
      this.loadRuns()
      this.loadArtifacts()
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
    },

    async deleteProject(p) {
      if (!confirm(`Projekt "${p.name}" samt Runs löschen?`)) return
      try { await fetch('/api/projects/' + encodeURIComponent(p.id), { method: 'DELETE' }) }
      catch (e) { console.error('deleteProject', e) }
      await this.loadProjects()
      if (this.activeProject && this.activeProject.id === p.id) {
        this.activeProject = null; this.runs = []; this.newRun()
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
        }
      } catch (e) { console.error('createRun', e) }
    },

    async openRun(r) {
      this.clearRun()
      this.activeRunId = r.id
      try {
        const res = await fetch('/api/agent/sessions/' + encodeURIComponent(r.id))
        if (res.ok) this._rehydrate((await res.json()).events || [])
      } catch (e) { console.error('openRun', e) }
      this.loadArtifacts()
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
      for (const e of events) {
        if (e.type === 'user') this.dialog.push({ role: 'user', text: e.text })
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
