import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import Flowable
import reportlab.rl_config

W, H = A4

# ─── COLOURS ────────────────────────────────────────────────────────────────
BG_DARK   = colors.HexColor('#0d0f14')
SURFACE   = colors.HexColor('#161a23')
SURFACE2  = colors.HexColor('#1e2332')
BORDER    = colors.HexColor('#2a3045')
ACCENT    = colors.HexColor('#6366f1')
ACCENT2   = colors.HexColor('#22d3ee')
ACCENT3   = colors.HexColor('#f59e0b')
GREEN     = colors.HexColor('#10b981')
ORANGE    = colors.HexColor('#f97316')
PURPLE    = colors.HexColor('#a855f7')
RED_TAG   = colors.HexColor('#ff6680')
TEAL_TAG  = colors.HexColor('#2de0cc')
ML_TAG    = colors.HexColor('#c084fc')
TEXT      = colors.HexColor('#e2e8f0')
TEXT2     = colors.HexColor('#94a3b8')
TEXT3     = colors.HexColor('#64748b')
WHITE     = colors.white
BLACK     = colors.black

MONO = 'Courier'
SANS = 'Helvetica'

# ─── STYLES ─────────────────────────────────────────────────────────────────
def S(name, **kw):
    base = dict(fontName=SANS, fontSize=10, leading=15, textColor=TEXT2,
                spaceAfter=4, spaceBefore=0)
    base.update(kw)
    return ParagraphStyle(name, **base)

styles = {
    'title':      S('title',   fontName=SANS+'-Bold',  fontSize=26, textColor=TEXT,   leading=32, spaceAfter=6),
    'subtitle':   S('subtitle',fontName=SANS,           fontSize=12, textColor=TEXT2,  leading=18, spaceAfter=0),
    'eyebrow':    S('eyebrow', fontName=SANS+'-Bold',   fontSize=8,  textColor=ACCENT, leading=12, spaceAfter=4, spaceBefore=18),
    'h1':         S('h1',      fontName=SANS+'-Bold',   fontSize=18, textColor=TEXT,   leading=24, spaceAfter=6, spaceBefore=20),
    'h2':         S('h2',      fontName=SANS+'-Bold',   fontSize=13, textColor=TEXT,   leading=18, spaceAfter=4, spaceBefore=14),
    'h3':         S('h3',      fontName=SANS+'-Bold',   fontSize=11, textColor=ACCENT2,leading=16, spaceAfter=3, spaceBefore=10),
    'body':       S('body',    fontName=SANS,           fontSize=10, textColor=TEXT2,  leading=16, spaceAfter=6),
    'body_bold':  S('body_b',  fontName=SANS+'-Bold',   fontSize=10, textColor=TEXT,   leading=16, spaceAfter=4),
    'code':       S('code',    fontName=MONO,           fontSize=8.5,textColor=colors.HexColor('#e2e8f0'), leading=13, spaceAfter=0, leftIndent=0),
    'code_cm':    S('code_cm', fontName=MONO,           fontSize=8.5,textColor=TEXT3,  leading=13, spaceAfter=0),
    'bullet':     S('bullet',  fontName=SANS,           fontSize=10, textColor=TEXT2,  leading=15, spaceAfter=3, leftIndent=14, bulletIndent=2),
    'small':      S('small',   fontName=SANS,           fontSize=8.5,textColor=TEXT3,  leading=13, spaceAfter=2),
    'toc_h':      S('toc_h',   fontName=SANS+'-Bold',   fontSize=10, textColor=TEXT,   leading=15, spaceAfter=2),
    'toc_item':   S('toc_item',fontName=SANS,           fontSize=9,  textColor=TEXT2,  leading=14, leftIndent=10, spaceAfter=1),
    'cover_tag':  S('ctag',    fontName=SANS+'-Bold',   fontSize=8,  textColor=ACCENT, leading=12, alignment=TA_CENTER),
}

def body(txt):   return Paragraph(txt, styles['body'])
def h1(txt):     return Paragraph(txt, styles['h1'])
def h2(txt):     return Paragraph(txt, styles['h2'])
def h3(txt):     return Paragraph(txt, styles['h3'])
def eyebrow(txt):return Paragraph(txt.upper(), styles['eyebrow'])
def sp(n=6):     return Spacer(1, n)
def hr():        return HRFlowable(width='100%', thickness=0.5, color=BORDER, spaceAfter=10, spaceBefore=4)

# ─── DARK CODE BLOCK ────────────────────────────────────────────────────────
class CodeBlock(Flowable):
    def __init__(self, lines, label='', label_color=ACCENT2):
        super().__init__()
        self.lines = lines          # list of (text, color)
        self.label = label
        self.label_color = label_color
        self._w = 0
        self._h = 0

    def wrap(self, avail_w, avail_h):
        self._w = avail_w
        pad_v = 10
        label_h = 14 if self.label else 0
        line_h = 13
        self._h = pad_v * 2 + label_h + len(self.lines) * line_h
        return self._w, self._h

    def draw(self):
        c = self.canv
        pad = 12
        pad_v = 10
        label_h = 14 if self.label else 0
        line_h = 13
        h = self._h

        # Background
        c.setFillColor(colors.HexColor('#0a0c12'))
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.5)
        c.roundRect(0, 0, self._w, h, 6, fill=1, stroke=1)

        # Label
        if self.label:
            c.setFont(SANS+'-Bold', 7)
            c.setFillColor(self.label_color)
            c.drawString(pad, h - pad_v - 8, self.label)

        # Code lines
        y = h - pad_v - label_h - line_h + 2
        for (text, col) in self.lines:
            c.setFont(MONO, 8.5)
            c.setFillColor(col)
            # Clip text to width
            c.drawString(pad, y, text[:110])
            y -= line_h

# helper to parse a code string into coloured lines
def parse_code(raw, label='', lang='py'):
    label_color = colors.HexColor('#f7c948') if lang == 'py' else colors.HexColor('#3178c6')
    lines = []
    kw_py  = {'async','await','def','class','return','if','not','or','and',
               'else','for','raise','try','except','pass','import','from','with','in','yield'}
    kw_ts  = {'const','let','var','return','if','else','import','export',
               'async','await','new','true','false','null','undefined','class',
               'private','public','this','from','of','get'}
    keywords = kw_py if lang == 'py' else kw_ts

    for raw_line in raw.split('\n'):
        stripped = raw_line
        # comment
        if stripped.lstrip().startswith('#') or stripped.lstrip().startswith('//'):
            lines.append((stripped, TEXT3))
        else:
            # simple heuristic: keyword-first lines
            first_word = stripped.lstrip().split('(')[0].split(' ')[0].split(':')[0]
            if first_word in keywords:
                lines.append((stripped, colors.HexColor('#c792ea')))
            elif stripped.lstrip().startswith('@'):
                lines.append((stripped, colors.HexColor('#c792ea')))
            elif stripped.lstrip().startswith('class '):
                lines.append((stripped, colors.HexColor('#ffcb6b')))
            else:
                lines.append((stripped, TEXT))
    return CodeBlock(lines, label=label, label_color=label_color)

# ─── CONCEPT BOX ────────────────────────────────────────────────────────────
class ConceptBox(Flowable):
    def __init__(self, text, kind='info'):  # kind: info | warn | tip
        super().__init__()
        self.text = text
        self.kind = kind
        self._w = 0; self._h = 0
        colors_map = {'info': ACCENT, 'warn': ACCENT3, 'tip': GREEN}
        bg_map = {'info': '#161d33', 'warn': '#1f1a0a', 'tip': '#0a1f18'}
        self.accent = colors_map.get(kind, ACCENT)
        self.bg = colors.HexColor(bg_map.get(kind, '#161d33'))

    def wrap(self, avail_w, avail_h):
        self._w = avail_w
        # estimate height from text length
        chars_per_line = int((avail_w - 40) / 5.5)
        n_lines = max(1, len(self.text) // chars_per_line + self.text.count('\n') + 1)
        self._h = 16 + n_lines * 14
        return self._w, self._h

    def draw(self):
        c = self.canv
        c.setFillColor(self.bg)
        c.setStrokeColor(self.accent)
        c.setLineWidth(0.5)
        c.roundRect(0, 0, self._w, self._h, 5, fill=1, stroke=1)
        c.setFillColor(self.accent)
        c.setLineWidth(2)
        c.line(0, 0, 0, self._h)
        c.setFont(SANS, 8.5)
        c.setFillColor(TEXT2)
        # wrap text manually
        words = self.text.split()
        line = ''; x = 10; y = self._h - 14; max_w = self._w - 20
        for w in words:
            test = line + (' ' if line else '') + w
            if c.stringWidth(test, SANS, 8.5) < max_w:
                line = test
            else:
                c.drawString(x, y, line); y -= 13; line = w
        if line:
            c.drawString(x, y, line)


# ─── PAGE BACKGROUND ────────────────────────────────────────────────────────
def dark_bg(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(BG_DARK)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    # left accent stripe
    canvas.setFillColor(colors.HexColor('#1e2332'))
    canvas.rect(0, 0, 4, H, fill=1, stroke=0)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, 0, 4, 60, fill=1, stroke=0)
    # footer
    canvas.setFont(SANS, 7)
    canvas.setFillColor(TEXT3)
    canvas.drawString(20*mm, 10*mm, 'Smart Supply Chain — Codebase Learning Guide')
    canvas.drawRightString(W - 20*mm, 10*mm, f'Page {doc.page}')
    canvas.restoreState()


# ─── COVER PAGE ─────────────────────────────────────────────────────────────
def cover_page():
    story = []
    story.append(Spacer(1, 60))

    # big title block
    story.append(Paragraph('<b>Smart Supply Chain</b>', ParagraphStyle(
        'cov1', fontName=SANS+'-Bold', fontSize=36, textColor=TEXT, leading=42, spaceAfter=6)))
    story.append(Paragraph('Codebase Learning Guide', ParagraphStyle(
        'cov2', fontName=SANS, fontSize=20, textColor=ACCENT, leading=26, spaceAfter=4)))
    story.append(Paragraph('Angular 21 &nbsp;·&nbsp; FastAPI &nbsp;·&nbsp; MongoDB &nbsp;·&nbsp; Prophet &nbsp;·&nbsp; KNN &nbsp;·&nbsp; Ollama', ParagraphStyle(
        'cov3', fontName=SANS, fontSize=11, textColor=TEXT3, leading=16, spaceAfter=30)))

    story.append(HRFlowable(width='100%', thickness=0.5, color=BORDER, spaceAfter=30))

    # what this guide covers
    story.append(Paragraph('What this guide covers', ParagraphStyle(
        'covh', fontName=SANS+'-Bold', fontSize=13, textColor=TEXT, leading=18, spaceAfter=10)))

    items = [
        ('🔐', 'Auth Service & JWT Flow',      'BehaviorSubject, RxJS operators, token lifecycle'),
        ('🗺️', 'Routing & Guards',             'CanActivateFn, role-based redirects, undefined filtering'),
        ('📦', 'Sales Order Component',        'Parallel HTTP, computed getters, scatter plot, calendar'),
        ('📈', 'Demand Forecast Component',    'loadId pattern, stddev thresholds, polling'),
        ('⚡', 'FastAPI Setup & CORS',          'Lifespan hooks, middleware, router prefixes'),
        ('🎟️', 'JWT Authentication',           'Token creation, Depends(), password hashing'),
        ('📐', 'Pydantic Models',              'Base → Create → Out pattern, automatic field filtering'),
        ('🍃', 'MongoDB & Motor',              'Async queries, singleton pattern, _id conversion'),
        ('📊', 'KPI Router',                  'BackgroundTasks, enriched order data, anomaly status'),
        ('🤖', 'KNN Anomaly Detection',        'Feature vectors, pkl model, fraud classification'),
        ('🔮', 'Prophet Forecasting',          'log1p, asyncio.to_thread, 90-day horizon'),
        ('💬', 'Local LLM via Ollama',         'Model selection, graceful fallback, prompt engineering'),
        ('🔄', 'HTTP + Token Full Flow',       'End-to-end request lifecycle, expiry handling'),
        ('🔨', 'Rebuild Checklist',            '4-phase step-by-step rebuild guide'),
    ]

    tbl_data = []
    for icon, title, desc in items:
        tbl_data.append([
            Paragraph(f'<b>{icon} {title}</b>', ParagraphStyle('ti', fontName=SANS+'-Bold', fontSize=9, textColor=TEXT, leading=13)),
            Paragraph(desc, ParagraphStyle('td', fontName=SANS, fontSize=8.5, textColor=TEXT3, leading=13)),
        ])

    tbl = Table(tbl_data, colWidths=[75*mm, 95*mm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), SURFACE),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [SURFACE, SURFACE2]),
        ('GRID', (0,0), (-1,-1), 0.4, BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROUNDEDCORNERS', [4]),
    ]))
    story.append(tbl)
    story.append(PageBreak())
    return story


# ─── SECTION: FILE STRUCTURE ─────────────────────────────────────────────────
def section_structure():
    s = []
    s.append(eyebrow('Start Here'))
    s.append(h1('Project Overview & File Structure'))
    s.append(body('A Smart Supply Chain Dashboard — a full-stack web app for tracking orders, detecting fraud, forecasting demand, and generating AI summaries using a local LLM. Here is every file and what it actually does.'))
    s.append(sp(8))
    s.append(h2('Tech Stack'))

    stack = [
        ['Layer', 'Technology', 'Role in this project'],
        ['Frontend',    'Angular 21 (standalone)',  'SPA, components, services, reactive forms'],
        ['Backend',     'FastAPI (Python)',          'Async REST API, JWT auth, CORS'],
        ['Database',    'MongoDB + Motor',           'Stores orders, products, forecasts, users'],
        ['Auth',        'JWT (python-jose)',         'Signed token issued on login, sent on every API call'],
        ['ML',          'scikit-learn (KNN)',        'Detects unusual/fraud orders by feature similarity'],
        ['Forecasting', 'Prophet (Meta)',            'Time-series demand prediction, retrains in background'],
        ['AI Text',     'Ollama (local LLM)',        'Generates natural language summaries — qwen2.5/llama3'],
    ]
    t = Table(stack, colWidths=[32*mm, 42*mm, 90*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), ACCENT),
        ('TEXTCOLOR', (0,0), (-1,0), WHITE),
        ('FONTNAME', (0,0), (-1,0), SANS+'-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8.5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [SURFACE, SURFACE2]),
        ('TEXTCOLOR', (0,1), (-1,-1), TEXT2),
        ('GRID', (0,0), (-1,-1), 0.4, BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 7),
    ]))
    s.append(t)
    s.append(sp(12))
    s.append(h2('Full File Structure'))

    fe = """-- FRONTEND (Angular 21) --
src/
  services/
    auth.ts          <- Auth service: login, logout, token, userState$
  app/
    app.config.ts    <- provideRouter + provideHttpClient
    app.routes.ts    <- All routes and which guard protects them
    auth.guard.ts    <- Blocks unauthenticated users, redirects to /login
    login.guard.ts   <- Redirects already-logged-in users away from /login
    login/           <- Login form component (email, password, signals)
    sales-order/     <- Orders dashboard (most complex component)
    demand-forecast/ <- Forecast calendar + chart component
    admin-dashboard/ <- Admin panel (placeholder, empty component)
    chatbot/         <- Chatbot (placeholder)
    supplier/        <- Supplier view (placeholder)"""

    be = """-- BACKEND (FastAPI) --
app/
  main.py            <- Entry: CORS middleware, lifespan, router registration
  core/
    config.py        <- Settings via pydantic-settings: JWT secret, MongoDB URI
    database.py      <- MongoDB connection singleton + get_db() dependency
    security.py      <- Password hashing (pbkdf2) + JWT token creation
  routers/
    auth.py          <- POST /api/auth/login, GET /api/auth/me
    users.py         <- CRUD for admin users (list, create, get, update, delete)
    kpis.py          <- Orders, purchases, products, forecasts, AI explain
  services/
    auth_service.py  <- get_current_admin() dependency (token -> user lookup)
    forecast_service.py <- Prophet retrain + LLM explanation generation
  models/
    user.py          <- Pydantic schemas: AdminBase/Create/Out, LoginRequest
    kpi.py           <- Schemas: AnomalyRecord, RFMRecord, DemandForecast
    order.py         <- Schema: SalesOrder with order_lines[]
    product.py       <- Schema: Product and Department"""

    s.append(parse_code(fe, label='Frontend Structure', lang='ts'))
    s.append(sp(8))
    s.append(parse_code(be, label='Backend Structure', lang='py'))
    s.append(PageBreak())
    return s


# ─── SECTION: ANGULAR CONCEPTS ───────────────────────────────────────────────
def section_angular_concepts():
    s = []
    s.append(eyebrow('Angular Frontend'))
    s.append(h1('Angular Concepts Used in This Project'))
    s.append(body('You already know two-way binding, services, and routing. Here are the more advanced patterns your project uses and exactly why.'))
    s.append(sp(6))

    # --- BehaviorSubject ---
    s.append(h2('BehaviorSubject — The Auth State Container'))
    s.append(body('A BehaviorSubject is a special kind of Observable that always holds the latest value and immediately gives it to new subscribers. It is the core of your auth system.'))
    s.append(parse_code("""// In auth.ts — three possible states:
//   undefined  -> app just loaded, still checking token
//   null       -> checked, no valid session
//   UserState  -> checked, user is logged in

private userStateSubject = new BehaviorSubject<UserState | null | undefined>(undefined);
public userState$ = this.userStateSubject.asObservable();

// Updating state — pushes new value to all subscribers:
this.userStateSubject.next(null);  // logged out
this.userStateSubject.next(user);  // logged in""", label='auth.ts — BehaviorSubject', lang='ts'))
    s.append(ConceptBox("Why undefined as the initial value? Because null means 'logged out' and undefined means 'don't know yet'. Guards filter out undefined so they never accidentally redirect while the auth check is still in progress.", 'info'))
    s.append(sp(10))

    # --- RxJS operators ---
    s.append(h2('RxJS Operators Used'))
    ops = [
        ['Operator', 'What it does', 'Where used in your code'],
        ['tap(fn)',        'Run side effect without changing the stream',       'Save token to localStorage after login'],
        ['switchMap(fn)',  'Replace stream with a new Observable',              'After login: switch to fetchCurrentUser() call'],
        ['catchError(fn)', 'Handle errors, return fallback Observable',         'If /auth/me fails: logout + return of(null)'],
        ['of(value)',      'Create Observable that emits one value immediately', 'Return null when no token exists'],
        ['map(fn)',        'Transform each emitted value',                       'Convert user object to true/false in checkAuth()'],
        ['filter(fn)',     'Only pass values that match condition',              'Guards: skip undefined, wait for real auth state'],
        ['take(1)',        'Complete after first emission',                      'Guards only need to check once, not keep watching'],
        ['pipe(...ops)',   'Chain multiple operators together',                  'Used on every HTTP call in auth.ts'],
    ]
    t = Table(ops, colWidths=[28*mm, 66*mm, 68*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1a1f35')),
        ('TEXTCOLOR', (0,0), (-1,0), ACCENT2),
        ('FONTNAME', (0,0), (-1,0), SANS+'-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [SURFACE, SURFACE2]),
        ('TEXTCOLOR', (0,1), (-1,-1), TEXT2),
        ('FONTNAME', (0,1), (0,-1), MONO),
        ('GRID', (0,0), (-1,-1), 0.4, BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
    ]))
    s.append(t)
    s.append(sp(10))

    # --- inject() ---
    s.append(h2('inject() — Modern Angular DI'))
    s.append(body('Your project uses the newer inject() function instead of constructor injection. Both do the same thing — inject() just works without a constructor, which is cleaner for standalone components and guard functions.'))
    s.append(parse_code("""// Old style (still valid):
constructor(private auth: Auth, private router: Router) {}

// New style (used in your project):
private auth = inject(Auth);
private router = inject(Router);
// No constructor needed at all""", label='Dependency Injection styles', lang='ts'))
    s.append(sp(10))

    # --- Signals ---
    s.append(h2('Signals — New State Primitives'))
    s.append(body('The Login component uses Angular Signals for errorMessage and isLoading. Signals are simpler than BehaviorSubject for local component state — no subscribe() needed.'))
    s.append(parse_code("""// Declare a signal with initial value:
errorMessage = signal<string | null>(null);
isLoading    = signal<boolean>(false);

// Update it:
this.errorMessage.set('Please fill out all fields.');
this.isLoading.set(true);

// Read it in template (no async pipe needed):
// {{ errorMessage() }}    <- Note: called as a function""", label='login.ts — Signals', lang='ts'))
    s.append(sp(10))

    # --- Standalone components ---
    s.append(h2('Standalone Components (Angular 21)'))
    s.append(body('Your project uses standalone components — the modern Angular approach. Each component declares its own imports instead of a shared NgModule file.'))
    s.append(parse_code("""@Component({
  selector: 'app-sales-order',
  standalone: true,           // <- no NgModule file needed
  imports: [CommonModule,     // <- *ngIf, *ngFor, pipes
            FormsModule],     // <- [(ngModel)] two-way binding
  templateUrl: './sales-order.html',
  styleUrl: './sales-order.css',
})
export class SalesOrder implements OnInit {
  ngOnInit(): void {
    this.loadDashboardData(); // called once when component mounts
  }
}""", label='Standalone component pattern', lang='ts'))
    s.append(sp(10))

    # --- Getters ---
    s.append(h2('Computed Getters — Live Derived State'))
    s.append(body('The sales order component uses TypeScript getters for filtered and paginated orders. Angular re-evaluates these on every change detection cycle, so the template always shows up-to-date data.'))
    s.append(parse_code("""// Getter = computed property, no () in template
get filteredOrders(): any[] {
  const q = this.tableSearchQuery.toLowerCase();
  if (!q) return this.orders;
  return this.orders.filter(o =>
    o.id.toString().includes(q) || o.status.toLowerCase().includes(q)
  );
}

get paginatedOrders(): any[] {
  const start = (this.currentPage - 1) * this.pageSize;
  return this.filteredOrders.slice(start, start + this.pageSize);
}

// In template: *ngFor="let order of paginatedOrders"
// NOT: paginatedOrders()  <- no parentheses needed""", label='sales-order.ts — Getters', lang='ts'))

    s.append(PageBreak())
    return s


# ─── SECTION: AUTH FULL ───────────────────────────────────────────────────────
def section_auth_full():
    s = []
    s.append(eyebrow('Angular Frontend — services/auth.ts'))
    s.append(h1('Auth Service — Full Breakdown'))
    s.append(body('The Auth service is the single source of truth for authentication state in the entire app. Every guard, component, and HTTP call that needs to know "am I logged in?" goes through this service.'))
    s.append(sp(6))

    s.append(h2('Login Flow — Step by Step'))
    s.append(parse_code("""login(email: string, password: string): Observable<UserState | null> {
  return this.http.post<{ access_token: string }>(
    `${this.apiUrl}/auth/login`,
    { email, password }          // Step 1: POST credentials
  ).pipe(
    tap(response => {
      localStorage.setItem('access_token', response.access_token);
    }),                          // Step 2: Save token (side effect)
    switchMap(() => this.fetchCurrentUser())  // Step 3: Who am I?
  );
}""", label='auth.ts — login()', lang='ts'))
    s.append(body('After login: the token is in localStorage, and userState$ emits the full user object. Any component or guard subscribed to userState$ immediately sees the change.'))
    s.append(sp(8))

    s.append(h2('Session Restore on App Load'))
    s.append(body('When the Angular app starts, the Auth service constructor runs immediately. It checks if there is a saved token and validates it against the backend — so refreshing the page does not log you out.'))
    s.append(parse_code("""constructor() {
  this.checkAuth().subscribe(); // always runs on startup
}

fetchCurrentUser(): Observable<UserState | null> {
  const token = localStorage.getItem('access_token');
  if (!token) {
    this.userStateSubject.next(null); // no token = logged out
    return of(null);
  }
  const headers = new HttpHeaders({ 'Authorization': `Bearer ${token}` });
  return this.http.get<UserState>(`${this.apiUrl}/auth/me`, { headers }).pipe(
    tap(user => this.userStateSubject.next(user)),  // update state
    catchError(() => {
      this.logout();   // bad token -> clean up
      return of(null);
    })
  );
}""", label='auth.ts — checkAuth() + fetchCurrentUser()', lang='ts'))
    s.append(sp(8))

    s.append(h2('Route Guards'))
    s.append(parse_code("""// authGuard — blocks unauthenticated access
export const authGuard: CanActivateFn = (route, state) => {
  const auth   = inject(Auth);
  const router = inject(Router);
  return auth.userState$.pipe(
    filter(user => user !== undefined), // wait for auth check to finish
    take(1),                            // only check once
    map(user => {
      if (user) return true;            // logged in -> allow
      router.navigate(['/login']);      // not logged in -> redirect
      return false;
    })
  );
};

// loginGuard — redirects already-logged-in users + role routing
map(user => {
  if (user) {
    if (user.role === 'supplier') router.navigate(['/supplier']);
    else                          router.navigate(['/']);
    return false; // don't show the login page
  }
  return true;    // not logged in -> show login
})""", label='auth.guard.ts + login.guard.ts', lang='ts'))
    s.append(ConceptBox("Key insight: the filter(user !== undefined) is what prevents a race condition. Without it, a guard could see undefined (still loading) and assume nobody is logged in, causing an unwanted redirect to /login.", 'warn'))

    s.append(PageBreak())
    return s


# ─── SECTION: SALES ORDER ─────────────────────────────────────────────────────
def section_sales_order():
    s = []
    s.append(eyebrow('Angular Frontend — sales-order component'))
    s.append(h1('Sales Order Component'))
    s.append(body('The most complex component in the project. It fetches orders, enriches them with computed values, builds a scatter plot (pure SVG via coordinate math), renders a monthly calendar, and re-implements a mini KNN in TypeScript for visualisation.'))
    s.append(sp(6))

    s.append(h2('Parallel API Calls'))
    s.append(body('Three independent HTTP calls fire simultaneously in ngOnInit. They do not wait for each other — each updates its own part of the UI when it arrives.'))
    s.append(parse_code("""loadDashboardData(): void {
  const headers = new HttpHeaders({ 'Authorization': `Bearer ${token}` });

  // Call 1 — orders: triggers scatter plot and calendar build
  this.http.get<any[]>('http://127.0.0.1:8000/api/kpis/orders', { headers })
    .subscribe({
      next: (data) => {
        this.orders = data;
        this.buildScatterPlot();
        this.buildCalendarGrid();
      },
      error: (err) => console.error(err)
    });

  // Call 2 — purchases (fires independently, same time)
  this.http.get<any[]>('http://127.0.0.1:8000/api/kpis/purchases', { headers })
    .subscribe({ next: (data) => { this.purchases = data; } });

  // Call 3 — AI executive summary (may take a few seconds)
  this.http.get<any>('http://127.0.0.1:8000/api/kpis/overview/explain', { headers })
    .subscribe({ next: (res) => { this.aiExplanation = res.explanation; } });
}""", label='sales-order.ts — loadDashboardData()', lang='ts'))
    s.append(sp(8))

    s.append(h2('Client-side KNN Nearest Neighbour Explainer'))
    s.append(body('When you click a scatter point, the frontend computes which 5 orders are most similar — using Euclidean distance across 4 normalised features. This is NOT the backend model; it is a TypeScript reimplementation for visualisation only.'))
    s.append(parse_code("""computeNearestNeighbors(selectedPt: ScatterPoint): void {
  const normFn = (val, min, max) => (val - min) / (max - min || 1);

  const normSelected = {
    sales:  normFn(selectedOrder.total_sales,    this.minSales,    this.maxSales),
    margin: normFn(selectedOrder.profit_margin,  this.minProfit,   this.maxProfit),
    qty:    normFn(selectedOrder.total_quantity, this.minQty,      this.maxQty),
    delay:  normFn(selectedOrder.delay_delta,    this.minDelay,    this.maxDelay),
  };

  const distances = this.orders
    .filter(o => o.id !== selectedPt.id)
    .map(o => {
      const normO = { /* same normFn for each feature */ };
      const dist = Math.sqrt(
        (normSelected.sales  - normO.sales)  ** 2 +
        (normSelected.margin - normO.margin) ** 2 +
        (normSelected.qty    - normO.qty)    ** 2 +
        (normSelected.delay  - normO.delay)  ** 2
      );
      return { order: o, dist };
    });

  distances.sort((a, b) => a.dist - b.dist);
  this.nearestNeighbors = distances.slice(0, 5);
}""", label='sales-order.ts — computeNearestNeighbors()', lang='ts'))
    s.append(sp(8))

    s.append(h2('Calendar Grid Builder'))
    s.append(body('The calendar is built entirely in TypeScript — no library. It calculates which day of the week each month starts on, fills in trailing/leading days from adjacent months, then maps order events to date strings.'))
    s.append(parse_code("""buildCalendarGrid(): void {
  const firstDayIndex = new Date(year, month, 1).getDay(); // 0=Sun
  const numDays = new Date(year, month + 1, 0).getDate();  // last day of month

  // Fill trailing days from previous month
  for (let i = firstDayIndex - 1; i >= 0; i--) { ... }
  // Fill current month days + attach events
  for (let i = 1; i <= numDays; i++) {
    const dateStr = `${year}-${pad(month+1)}-${pad(i)}`;
    cells.push({ dayNumber: i, isCurrentMonth: true,
                 events: getEventsForDate(dateStr) });
  }
  // Fill leading days to reach 35 or 42 cells total
}""", label='sales-order.ts — buildCalendarGrid()', lang='ts'))
    s.append(PageBreak())
    return s


# ─── SECTION: DEMAND FORECAST ─────────────────────────────────────────────────
def section_demand_forecast():
    s = []
    s.append(eyebrow('Angular Frontend — demand-forecast component'))
    s.append(h1('Demand Forecast Component'))
    s.append(body('This component handles product selection, fetches Prophet forecasts, builds the chart, and populates the calendar with predicted stockout events. It has the most complex async patterns in the project.'))
    s.append(sp(6))

    s.append(h2('The Load ID Anti-Stale Pattern'))
    s.append(body('If the user switches products quickly, responses from older requests can arrive after newer ones. The load ID pattern detects and ignores stale responses.'))
    s.append(parse_code("""private _currentLoadId = 0;

loadEventsAndBuildCalendar(): void {
  const loadId = ++this._currentLoadId; // new ID for this call

  // Safety timer: stop spinner after 5s even if API is slow
  this._safetyTimer = setTimeout(() => {
    if (loadId !== this._currentLoadId) return; // stale? ignore
    this.isLoadingCalendar = false;
    this.buildCalendarEvents([], []);
  }, 5000);

  this.http.get(`/api/kpis/forecasts?product_id=${this.selectedProductId}`)
    .pipe(timeout(15000))
    .subscribe({
      next: (forecasts) => {
        if (loadId !== this._currentLoadId) return; // user switched product
        clearTimeout(this._safetyTimer);
        this.buildCalendarEvents(forecasts);
        this.isLoadingCalendar = false;
      }
    });
}""", label='demand-forecast.ts — loadId pattern', lang='ts'))
    s.append(ConceptBox("Without the loadId check: click Product A, then quickly click Product B. If Product A's slower response arrives after Product B's, it overwrites the screen with Product A's data. The loadId detects this and discards the stale response.", 'warn'))
    s.append(sp(8))

    s.append(h2('Dynamic Thresholds using Standard Deviation'))
    s.append(body('Instead of a fixed number to define "high demand", the component calculates it dynamically each month based on that product and month\'s distribution.'))
    s.append(parse_code("""const values = monthForecasts.map(f => f.forecast);
const mean   = values.reduce((s, v) => s + v, 0) / values.length;
const stdDev = Math.sqrt(
  values.reduce((s, v) => s + (v - mean) ** 2, 0) / values.length
);

// 1.2 std deviations above average = high demand day
const highDemandThreshold = mean + 1.2 * stdDev;
// 1.7 std deviations above average = potential stockout
const stockoutThreshold   = mean + 1.7 * stdDev;""", label='demand-forecast.ts — dynamic thresholds', lang='ts'))
    s.append(sp(8))

    s.append(h2('Background Polling for Prophet Results'))
    s.append(body('After receiving forecasts, the component checks whether December data exists. If Prophet has not finished training yet, it re-polls every 2 seconds (up to 5 times).'))
    s.append(parse_code("""const hasDecemberForecasts = forecasts.some(
  f => f.sales === null && f.date >= '2017-12-01'
);

if (!hasDecemberForecasts && this.pollCount < 5) {
  this.pollCount++;
  // Try again in 2 seconds
  this._pollingTimer = setTimeout(() => {
    this.loadEventsAndBuildCalendar();
  }, 2000);
}""", label='demand-forecast.ts — polling', lang='ts'))
    s.append(PageBreak())
    return s


# ─── SECTION: FASTAPI ─────────────────────────────────────────────────────────
def section_fastapi():
    s = []
    s.append(eyebrow('FastAPI Backend'))
    s.append(h1('FastAPI Setup, CORS & Routing'))
    s.append(body('How the backend boots, connects to MongoDB on startup, and registers all routes under the /api prefix.'))
    s.append(sp(6))

    s.append(h2('Lifespan — Startup and Shutdown'))
    s.append(parse_code("""@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_connection.connect_to_database()  # runs on startup
    yield                                       # app runs here
    await db_connection.close_database_connection()  # on shutdown

app = FastAPI(title="Smart Supply Chain Backend", lifespan=lifespan)""", label='main.py — lifespan', lang='py'))
    s.append(ConceptBox("The yield is the key. Code before yield = startup. Code after yield = shutdown. This is the modern FastAPI way to manage resources that need to open and close around the app's lifetime.", 'tip'))
    s.append(sp(8))

    s.append(h2('CORS Middleware'))
    s.append(parse_code("""app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",      # Angular dev server
        "http://127.0.0.1:4200",
    ],
    allow_credentials=True,   # required for Authorization headers
    allow_methods=["*"],       # GET, POST, PUT, DELETE, OPTIONS, etc.
    allow_headers=["*"],       # including Authorization
)""", label='main.py — CORS', lang='py'))
    s.append(ConceptBox("REBUILD WARNING: If you deploy Angular on a different domain (e.g. Vercel), add that URL to allow_origins. Without it, every API call will fail silently in the browser with a CORS error.", 'warn'))
    s.append(sp(8))

    s.append(h2('Router Registration & Prefix Chaining'))
    s.append(parse_code("""# Each router file has its own inner prefix:
# auth.router   has prefix="/auth"   -> full path: /api/auth/login
# users.router  has prefix="/admins" -> full path: /api/admins/
# kpis.router   has prefix="/kpis"   -> full path: /api/kpis/orders

app.include_router(auth.router,  prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(kpis.router,  prefix="/api")""", label='main.py — router registration', lang='py'))
    s.append(sp(8))

    s.append(h2('Depends() — FastAPI Dependency Injection'))
    s.append(body('Depends() is FastAPI\'s way of sharing reusable logic across routes. When you add Depends(get_db) or Depends(get_current_admin) to a route parameter, FastAPI runs that function first and injects the result.'))
    s.append(parse_code("""# Dependency: provides a DB instance to any route that needs it
async def get_db():
    return db_connection.db

# Usage in a route: FastAPI calls get_db() automatically
@router.get("/orders")
async def list_orders(db = Depends(get_db), current_admin = Depends(get_current_admin)):
    # db is already connected, current_admin is already validated
    cursor = db["sales_orders"].find().limit(500)
    ...

# If get_current_admin raises HTTPException(401),
# the route function never runs at all.""", label='How Depends() works', lang='py'))
    s.append(PageBreak())
    return s


# ─── SECTION: JWT ─────────────────────────────────────────────────────────────
def section_jwt():
    s = []
    s.append(eyebrow('FastAPI Backend — Auth'))
    s.append(h1('JWT Authentication — Full Flow'))
    s.append(body('How a username + password becomes a signed token, and how that token proves identity on every subsequent request without touching the database for every check.'))
    s.append(sp(6))

    s.append(h2('What a JWT Contains'))
    s.append(parse_code("""# A JWT is three Base64-encoded parts joined by dots:
# header.payload.signature

# Decoded payload for your project:
{
  "sub": "60c72b2f9b1d8e2e4c8d9e01",  # admin's MongoDB _id
  "exp": 1719500000                    # expiry (Unix timestamp)
}

# The signature is created with:
#   HMACSHA256(header + "." + payload, JWT_SECRET_KEY)
# Only the server knows JWT_SECRET_KEY, so nobody can fake a token.""", label='JWT structure', lang='py'))
    s.append(sp(8))

    s.append(h2('Token Creation — security.py'))
    s.append(parse_code("""def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=120)
    to_encode = {"exp": expire, "sub": str(subject)}
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY,
                      algorithm="HS256")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)     # pbkdf2_sha256

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)""", label='core/security.py', lang='py'))
    s.append(sp(8))

    s.append(h2('Login Route — routers/auth.py'))
    s.append(parse_code("""@router.post("/login")
async def login(login_data: LoginRequest, db = Depends(get_db)):
    email = login_data.email.lower()
    admin = await db["admin"].find_one({"email": email})

    if not admin or not verify_password(login_data.password,
                                         admin["hashed_password"]):
        raise HTTPException(status_code=400,
                            detail="Incorrect email or password")

    access_token = create_access_token(subject=str(admin["_id"]))
    return {"access_token": access_token, "token_type": "bearer"}""", label='routers/auth.py', lang='py'))
    s.append(sp(8))

    s.append(h2('Token Validation — get_current_admin()'))
    s.append(parse_code("""async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db = Depends(get_db)
) -> dict:
    token = credentials.credentials  # "Bearer <token>" -> just token

    # Decode + verify the JWT signature
    payload = jwt.decode(token, settings.JWT_SECRET_KEY,
                         algorithms=["HS256"])
    admin_id = payload.get("sub")     # MongoDB _id string

    # Look up the admin in MongoDB
    admin = await db["admin"].find_one({"_id": ObjectId(admin_id)})
    if admin is None:
        raise HTTPException(status_code=401)

    admin["id"] = str(admin["_id"])
    return admin   # injected into every protected route""", label='services/auth_service.py', lang='py'))
    s.append(PageBreak())
    return s


# ─── SECTION: PYDANTIC + MONGODB ──────────────────────────────────────────────
def section_pydantic_mongo():
    s = []
    s.append(eyebrow('FastAPI Backend — Models & Database'))
    s.append(h1('Pydantic Models & MongoDB'))
    s.append(sp(4))

    s.append(h2('The Base → Create → Out Pattern'))
    s.append(body('Every entity in your project follows this three-class pattern. It controls exactly which fields appear in requests vs responses — and automatically hides sensitive data like hashed passwords.'))
    s.append(parse_code("""class AdminBase(BaseModel):
    email: EmailStr       # validated email format
    first_name: str
    last_name: str
    role: str = "admin"   # default value

class AdminCreate(AdminBase):
    password: str         # only needed when creating (POST body)

class AdminOut(AdminBase):
    id: str               # only sent in responses, never receives
    # NOTE: hashed_password is NOT here — Pydantic strips it from all responses
    class Config:
        populate_by_name = True""", label='models/user.py — Admin pattern', lang='py'))
    s.append(ConceptBox("Security by design: using AdminOut as response_model in the route decorator means FastAPI filters the MongoDB document through AdminOut before returning it. Even if the document has hashed_password, it never leaves the server.", 'tip'))
    s.append(sp(8))

    s.append(h2('Demand Forecast Model'))
    s.append(parse_code("""class DemandForecastBase(BaseModel):
    date: str                      # "YYYY-MM-DD"
    product_id: Optional[int] = None
    sales: Optional[float] = None  # None = future date (no actual sale)
    forecast: float                # Prophet's predicted value

# Angular uses sales == null to decide:
#   sales != null  -> draw solid "actual" line on chart
#   sales == null  -> draw dashed "forecast" line on chart""", label='models/kpi.py — DemandForecast', lang='py'))
    s.append(sp(8))

    s.append(h2('MongoDB + Motor — Async Queries'))
    s.append(parse_code("""# Find one document
admin = await db["admin"].find_one({"email": email})

# Find many — Motor returns an async cursor
records = []
async for doc in db["forecasts"].find(query).sort("date", 1).limit(2000):
    records.append(doc)

# Insert and capture the new _id
result = await db["admin"].insert_one(admin_dict)
new_id = str(result.inserted_id)

# Update one document
await db["admin"].update_one({"_id": ObjectId(id)}, {"$set": updates})

# Delete
await db["admin"].delete_one({"_id": ObjectId(id)})

# ALWAYS convert _id to string for JSON serialization:
doc["id"] = str(doc.pop("_id"))   # pop removes _id, sets id""", label='Motor async query patterns', lang='py'))
    s.append(ConceptBox("Motor is the async version of PyMongo. Every query uses await, so FastAPI can handle other requests while MongoDB is responding — no blocking.", 'info'))
    s.append(PageBreak())
    return s


# ─── SECTION: KPI ROUTER ──────────────────────────────────────────────────────
def section_kpi_router():
    s = []
    s.append(eyebrow('FastAPI Backend — routers/kpis.py'))
    s.append(h1('KPI Router — Orders, Forecasts & AI'))
    s.append(body('The largest router in the project. It enriches raw database records with computed fields, runs ML predictions, triggers background tasks, and calls the local LLM.'))
    s.append(sp(6))

    s.append(h2('Background Tasks for Non-Blocking Retraining'))
    s.append(parse_code("""@router.get("/forecasts")
async def list_forecasts(
    product_id: int,
    background_tasks: BackgroundTasks,  # injected by FastAPI
    db = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    # Check if December forecasts already exist
    has_future = await db["forecasts"].find_one({
        "product_id": product_id,
        "sales": None,
        "date": {"$gte": "2017-12-01"}
    })

    if not has_future:
        # Kick off Prophet retraining WITHOUT blocking the HTTP response
        background_tasks.add_task(retrain_demand_forecast, db, product_id)

    # Return current data immediately (Angular polls for updated results)
    cursor = db["forecasts"].find(query).sort("date", 1).limit(2000)
    return [format_mongo_doc(doc) async for doc in cursor]""", label='routers/kpis.py — BackgroundTasks', lang='py'))
    s.append(sp(8))

    s.append(h2('What /api/kpis/orders Computes'))
    s.append(body('The orders route does not just return raw documents. For each order it joins with the products collection, computes aggregate values, and runs the KNN model:'))

    computed = [
        ['Computed Field', 'How it is calculated'],
        ['category',       'Joins order_lines[0].product_sku with products collection'],
        ['total_quantity',  'Sum of order_lines[].quantity'],
        ['total_sales',     'Sum of quantity * unitPrice for each line'],
        ['profit_margin',   'order_profit / total_sales'],
        ['discount_ratio',  'Average discount across all order line products'],
        ['delay_delta',     'real_shipment - scheduled_shipment (negative = early)'],
        ['anomaly_status',  '"unusual" | "delay anomaly" | "valid" based on KNN + delay_delta'],
    ]
    t = Table(computed, colWidths=[45*mm, 120*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1a1f35')),
        ('TEXTCOLOR', (0,0), (-1,0), ACCENT2),
        ('FONTNAME', (0,0), (-1,0), SANS+'-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8.5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [SURFACE, SURFACE2]),
        ('TEXTCOLOR', (0,1), (-1,-1), TEXT2),
        ('FONTNAME', (0,1), (0,-1), MONO),
        ('GRID', (0,0), (-1,-1), 0.4, BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
    ]))
    s.append(t)
    s.append(PageBreak())
    return s


# ─── SECTION: ML ──────────────────────────────────────────────────────────────
def section_ml():
    s = []
    s.append(eyebrow('ML / AI Features'))
    s.append(h1('KNN Anomaly Detection'))
    s.append(body('K-Nearest Neighbors classifies each sales order as normal (valid), suspicious (unusual), or delayed. It works by comparing a new order to its most similar historical orders.'))
    s.append(sp(6))

    s.append(h2('How KNN Works in Plain English'))
    s.append(body('Imagine plotting every order on a graph with axes: sales value, profit margin, delivery delay, quantity. Fraudulent orders tend to cluster in unusual regions. KNN looks at an order\'s 5 closest neighbours and asks "are most of them fraud cases?" If yes, this order is probably fraud too.'))
    s.append(sp(6))

    s.append(h2('Feature Vector & Prediction'))
    s.append(parse_code("""# 5 features sent to the trained KNN model for each order
features_df = pd.DataFrame([[
    float(delay_delta),     # days late (real - scheduled)
    float(total_quantity),  # total units ordered
    float(total_sales),     # total monetary value
    float(profit_margin),   # profit / sales ratio
    float(discount_ratio),  # average discount across lines
]], columns=model_data["features"])

# Normalize using the same scaler used during training
features_scaled = scaler.transform(features_df)

# Predict: 0 = normal, 1 = fraud/unusual
is_knn_fraud = int(knn.predict(features_scaled)[0])

# Final status assignment:
if is_knn_fraud == 1 or doc.get("status") == "SUSPECTED_FRAUD":
    anomaly_status = "unusual"
elif delay_delta > 3:
    anomaly_status = "delay anomaly"
else:
    anomaly_status = "valid" """, label='routers/kpis.py — KNN prediction', lang='py'))
    s.append(sp(6))

    s.append(h2('The .pkl Model File'))
    s.append(parse_code("""# knn_anomaly_model.pkl contains a dict:
{
  "knn":      KNeighborsClassifier (trained model),
  "scaler":   StandardScaler (to normalize features identically to training),
  "features": ["delay_delta", "total_quantity", "total_sales",
               "profit_margin", "discount_ratio"]
}

# Loaded once at startup:
with open("knn_anomaly_model.pkl", "rb") as f:
    KNN_MODEL_DATA = pickle.load(f)""", label='KNN model structure', lang='py'))
    s.append(ConceptBox("REBUILD WARNING: The model path is hardcoded to C:\\Users\\Sabor\\Desktop\\... — a Windows absolute path. For any rebuild or deployment, change this to os.path.join(os.path.dirname(__file__), '../../processed_data/knn_anomaly_model.pkl') or use an environment variable.", 'warn'))
    s.append(sp(12))

    s.append(h1('Prophet Demand Forecasting'))
    s.append(body('Meta\'s Prophet library predicts future daily demand by learning trends and seasonal patterns from historical sales data. The full pipeline runs as a background task.'))
    s.append(sp(6))

    s.append(h2('Full Retraining Pipeline'))
    s.append(parse_code("""async def retrain_demand_forecast(db, product_id):
    # 1. Fetch historical sales from MongoDB (last 180 days max)
    cursor = db["forecasts"].find({"sales": {"$ne": None}, "product_id": product_id})
    records = [doc async for doc in cursor]

    # 2. Build DataFrame
    df = pd.DataFrame([{"ds": pd.to_datetime(r["date"]), "y": float(r["sales"])}
                       for r in records])
    df = df.groupby("ds").agg({"y": "sum"}).reset_index()

    # 3. Log-transform to handle skewed distributions
    df["y"] = np.log1p(df["y"])   # log(1 + y)

    # 4. Fit Prophet in a thread (avoids blocking the async event loop)
    model = Prophet(yearly_seasonality=False, weekly_seasonality=True,
                    uncertainty_samples=0)   # 0 = 5-10x faster
    await asyncio.to_thread(model.fit, df[['ds', 'y']])

    # 5. Predict next 90 days
    future = model.make_future_dataframe(periods=90, include_history=False)
    forecast = model.predict(future)

    # 6. Inverse transform: e^yhat - 1, clipped to 0
    forecast['yhat'] = np.expm1(forecast['yhat']).clip(lower=0.0)

    # 7. Save future forecasts to MongoDB (replace previous ones)
    await db["forecasts"].delete_many({"sales": None, "product_id": product_id})
    await db["forecasts"].insert_many([...new 90-day documents...])""", label='services/forecast_service.py — retraining', lang='py'))
    s.append(sp(6))

    s.append(h2('Performance Optimisations Used'))
    opts = [
        ['Optimisation', 'Effect'],
        ['uncertainty_samples=0',        '5-10x speedup — skips confidence interval computation'],
        ['Last 180 days only',           'Caps training data to prevent slow training on large datasets'],
        ['asyncio.to_thread(model.fit)', 'Runs CPU-heavy fit() in thread pool, does not block the async loop'],
        ['include_history=False',        'make_future_dataframe() only generates future dates, not history'],
        ['log1p / expm1 transform',      'Compresses skewed sales data for better model fit, inverts after predict'],
    ]
    t = Table(opts, colWidths=[65*mm, 99*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1a1f35')),
        ('TEXTCOLOR', (0,0), (-1,0), ACCENT2),
        ('FONTNAME', (0,0), (-1,0), SANS+'-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8.5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [SURFACE, SURFACE2]),
        ('TEXTCOLOR', (0,1), (-1,-1), TEXT2),
        ('GRID', (0,0), (-1,-1), 0.4, BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
    ]))
    s.append(t)
    s.append(PageBreak())
    return s


# ─── SECTION: OLLAMA ──────────────────────────────────────────────────────────
def section_ollama():
    s = []
    s.append(eyebrow('ML / AI Features'))
    s.append(h1('Local LLM via Ollama'))
    s.append(body('Both AI summary endpoints — the supply chain overview and the per-product forecast explanation — call a locally running Ollama instance. No external API, no cost, fully private.'))
    s.append(sp(6))

    s.append(h2('How Ollama is Called'))
    s.append(parse_code("""async with httpx.AsyncClient(timeout=60.0) as client:
    # 1. Discover which models are installed locally
    models_resp = await client.get("http://localhost:11434/api/tags")
    installed = [m["name"] for m in models_resp.json().get("models", [])]

    # 2. Pick the best available model (preference order)
    preferred = ["qwen2.5:7b", "qwen2.5:latest", "llama3.1", "mistral"]
    model_to_use = next(
        (m for pref in preferred for m in installed if m.startswith(pref)),
        installed[0] if installed else "qwen2.5:7b"
    )

    # 3. Generate text (stream=False = wait for full response)
    response = await client.post("http://localhost:11434/api/generate", json={
        "model": model_to_use,
        "prompt": prompt,
        "stream": False
    })
    explanation = response.json().get("response", "").strip()""", label='Ollama API call pattern', lang='py'))
    s.append(sp(8))

    s.append(h2('Prompt Engineering Pattern'))
    s.append(parse_code("""prompt = (
    f"You are a supply chain AI analyst. Write a concise 2-3 sentence "
    f"executive summary of the current supply chain status.\\n"
    f"- Total sales orders analyzed: {total_orders}.\\n"
    f"- KNN unusual fraud transactions flagged: {unusual_count}.\\n"
    f"- Critical shipping delays detected: {len(delayed)}.\\n\\n"
    f"Write a professional summary. State numbers explicitly. "
    f"Do NOT use bullet points, markdown, or greetings."  # <- constraint
)""", label='Prompt structure in kpis.py', lang='py'))
    s.append(sp(8))

    s.append(h2('Graceful Fallback'))
    s.append(body('If Ollama is not running (no GPU, production server), the code catches the connection error and returns a rule-based template. The Angular frontend always receives a response — it never knows Ollama failed.'))
    s.append(parse_code("""try:
    explanation = await call_ollama(prompt)
    if explanation:
        return {"explanation": explanation}
except Exception:
    pass  # Ollama not running? No crash, no 500 error.

# Rule-based fallback (always works):
return {"explanation":
    f"KNN classifier flagged {unusual_count} unusual transactions. "
    f"Delayed orders: {delayed_orders_str}. Recommend immediate review."
}""", label='Graceful fallback pattern', lang='py'))
    s.append(PageBreak())
    return s


# ─── SECTION: FULL FLOW ───────────────────────────────────────────────────────
def section_full_flow():
    s = []
    s.append(eyebrow('Full Stack'))
    s.append(h1('Complete HTTP + Token Flow'))
    s.append(body('What actually happens, byte by byte, from the user clicking Login to seeing orders on screen.'))
    s.append(sp(6))

    s.append(h2('Step 1 — Login'))
    s.append(parse_code("""Angular sends:
  POST http://127.0.0.1:8000/api/auth/login
  Content-Type: application/json
  Body: { "email": "admin@example.com", "password": "secret" }

FastAPI responds:
  { "access_token": "eyJhbGci...", "token_type": "bearer" }

Angular stores:
  localStorage.setItem('access_token', 'eyJhbGci...')

Angular then calls fetchCurrentUser() with the new token:
  GET /api/auth/me
  Authorization: Bearer eyJhbGci...

FastAPI responds:
  { "id": "abc123", "email": "...", "role": "admin", ... }

BehaviorSubject emits the user object -> guards allow navigation -> redirect to /""", label='Full login sequence', lang='py'))
    s.append(sp(8))

    s.append(h2('Step 2 — Every Protected Request'))
    s.append(parse_code("""Angular reads token and builds headers:
  const headers = new HttpHeaders({
    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
  });

Angular sends:
  GET http://127.0.0.1:8000/api/kpis/orders
  Authorization: Bearer eyJhbGci...

FastAPI's get_current_admin() Dependency runs FIRST:
  1. HTTPBearer() extracts "Bearer eyJhbGci..." from the header
  2. jwt.decode() verifies signature + checks expiry
  3. Extracts "sub" = admin's MongoDB _id
  4. Fetches admin document from MongoDB
  5. Injects admin dict into the route handler

Route handler runs normally and returns data.""", label='Protected request lifecycle', lang='py'))
    s.append(sp(8))

    s.append(h2('Step 3 — Token Expiry'))
    s.append(parse_code("""Token expires after 120 minutes (config.py: ACCESS_TOKEN_EXPIRE_MINUTES = 120)

FastAPI responds with:
  401 Unauthorized
  { "detail": "Could not validate credentials" }

Angular's catchError in fetchCurrentUser():
  -> calls this.logout()
  -> logout() removes token from localStorage
  -> userStateSubject.next(null)
  -> authGuard sees null -> redirects to /login
  -> User sees the login page again""", label='Token expiry flow', lang='py'))
    s.append(PageBreak())
    return s


# ─── SECTION: REBUILD ─────────────────────────────────────────────────────────
def section_rebuild():
    s = []
    s.append(eyebrow('Rebuild Guide'))
    s.append(h1('How to Rebuild from Scratch'))
    s.append(body('If you had to rebuild this project from zero, here is the exact sequence — the right order matters because each phase depends on the previous one.'))
    s.append(sp(6))

    s.append(h2('Phase 1 — Backend Foundation'))
    phase1 = [
        'pip install fastapi uvicorn motor pydantic-settings python-jose passlib[bcrypt] python-multipart httpx',
        'Create core/config.py with pydantic-settings: JWT_SECRET_KEY, MONGODB_URI, DATABASE_NAME, ACCESS_TOKEN_EXPIRE_MINUTES',
        'Create core/database.py: AsyncIOMotorClient singleton, connect_to_database(), get_db() dependency function',
        'Create core/security.py: get_password_hash(), verify_password() with passlib, create_access_token() with python-jose',
        'Create models/user.py: AdminBase, AdminCreate, AdminOut (no password field!), LoginRequest with EmailStr',
        'Create services/auth_service.py: get_current_admin() that decodes JWT and looks up admin in MongoDB',
        'Create routers/auth.py: POST /login (verify password, return token) and GET /me (return current admin)',
        'Create main.py: FastAPI app with lifespan hook, CORSMiddleware for localhost:4200, include_router x3 with /api prefix',
        'Test with Swagger UI: run "uvicorn app.main:app --reload" and open http://localhost:8000/docs',
    ]
    for item in phase1:
        s.append(Paragraph(f'• {item}', styles['bullet']))
    s.append(sp(8))

    s.append(h2('Phase 2 — Angular Foundation'))
    phase2 = [
        'ng new front-end --standalone --routing (Angular 21+ uses standalone by default)',
        'In app.config.ts: add provideRouter(routes) and provideHttpClient() to providers array',
        'Create services/auth.ts: BehaviorSubject<UserState | null | undefined>(undefined), login(), logout(), fetchCurrentUser() called in constructor',
        'Create auth.guard.ts: filter(user !== undefined), take(1), map(user => user ? true : router.navigate(/login))',
        'Create login.guard.ts: same filter pattern, redirect logged-in users with role check (supplier -> /supplier, else -> /)',
        'Set up app.routes.ts: /login with canActivate:[loginGuard], parent "" with canActivate:[authGuard] and children',
        'Create Login component: [(ngModel)] on email/password, inject Auth, call auth.login().subscribe(), handle errors with signal<string|null>',
        'Test: ng serve, navigate to http://localhost:4200 — should redirect to /login. Login should redirect to /',
    ]
    for item in phase2:
        s.append(Paragraph(f'• {item}', styles['bullet']))
    s.append(sp(8))

    s.append(h2('Phase 3 — Feature Pages'))
    phase3 = [
        'Add kpis.py router with GET /orders: fetch sales_orders, join with products, compute total_sales/profit_margin/delay_delta',
        'Add GET /purchases, GET /products, GET /forecasts with optional product_id query param',
        'Add GET /overview/explain: compile stats, call Ollama, fallback to template string',
        'Create SalesOrder component: inject HttpClient + Auth, loadDashboardData() with 3 parallel HTTP calls, computed getters for filtered/paginated orders',
        'Add scatter plot: buildScatterPlot() maps each order to (cx, cy) coordinates using min-max normalisation',
        'Add calendar: buildCalendarGrid() calculates firstDayIndex, fills 35/42 cells, maps events to dateStr',
        'Create DemandForecast component: loadId pattern, safety timer, 5s polling, dynamic stddev thresholds for stockout',
    ]
    for item in phase3:
        s.append(Paragraph(f'• {item}', styles['bullet']))
    s.append(sp(8))

    s.append(h2('Phase 4 — ML Features'))
    phase4 = [
        'KNN Model: train in Jupyter (KNeighborsClassifier + StandardScaler), export with pickle.dump({"knn": model, "scaler": scaler, "features": names})',
        'Fix the hardcoded Windows model path: use os.path.join(os.path.dirname(__file__), "../../processed_data/knn_anomaly_model.pkl")',
        'Create services/forecast_service.py: retrain_demand_forecast() with log1p, asyncio.to_thread(model.fit), expm1 inverse, insert 90-day forecasts',
        'Add BackgroundTasks to GET /forecasts: if no December forecasts found, kick off retraining without blocking response',
        'Install Ollama: brew install ollama (Mac) or see ollama.com. Run "ollama pull qwen2.5:7b"',
        'Add generate_forecast_explanation() in forecast_service.py: build prompt with real numbers, call localhost:11434/api/generate, template fallback',
    ]
    for item in phase4:
        s.append(Paragraph(f'• {item}', styles['bullet']))
    s.append(sp(10))

    s.append(h2('Things to Fix in a Rebuild'))
    s.append(ConceptBox(
        "1. Hardcoded KNN model path to C:\\Users\\Sabor\\... — use a relative path or env variable.\n"
        "2. No Angular HTTP interceptor — every component manually adds the Bearer token header. Add an interceptor to do it automatically.\n"
        "3. API base URL is hardcoded as 'http://127.0.0.1:8000/api' in multiple files — move it to environment.ts.\n"
        "4. JWT secret is hardcoded in config.py — should only come from a .env file, never committed to git.\n"
        "5. Placeholder components (chatbot, insight, admin-dashboard, supplier) are completely empty.",
        'warn'
    ))
    return s


# ─── BUILD ────────────────────────────────────────────────────────────────────
def build_pdf(path):
    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=20*mm,
        rightMargin=20*mm,
        topMargin=18*mm,
        bottomMargin=22*mm,
    )

    story = []
    story += cover_page()
    story += section_structure()
    story += section_angular_concepts()
    story += section_auth_full()
    story += section_sales_order()
    story += section_demand_forecast()
    story += section_fastapi()
    story += section_jwt()
    story += section_pydantic_mongo()
    story += section_kpi_router()
    story += section_ml()
    story += section_ollama()
    story += section_full_flow()
    story += section_rebuild()

    doc.build(story, onFirstPage=dark_bg, onLaterPages=dark_bg)
    print(f"PDF written to {path}")

output_dir = os.path.join(os.path.dirname(__file__), 'outputs')
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, 'smart-supply-chain-guide.pdf')
build_pdf(output_path)