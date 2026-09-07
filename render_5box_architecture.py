import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Canvas with 16:9 ratio and transparent background
fig, ax = plt.subplots(figsize=(16, 8.5), dpi=300)
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis('off')

# Set background to transparent
fig.patch.set_alpha(0.0)
ax.patch.set_alpha(0.0)

# Minimalist component definitions with increased height for larger typography
components = [
    {
        'title': 'Frontend UI (Angular 17)',
        'x': 3, 'y': 50, 'w': 28, 'h': 45,
        'bullets': [
            'RxJS State Streams',
            'Chart.js Analytics',
            'FullCalendar Views',
            'Live Alert Banners'
        ]
    },
    {
        'title': 'API Gateway (FastAPI)',
        'x': 36, 'y': 50, 'w': 28, 'h': 45,
        'bullets': [
            'Async REST Endpoints',
            'Motor AsyncIO Driver',
            'Pydantic Validation',
            'CORS & Middleware'
        ]
    },
    {
        'title': 'Predictive ML Engines',
        'x': 69, 'y': 50, 'w': 28, 'h': 45,
        'bullets': [
            'Meta Prophet (Forecast)',
            'LightGBM (Anomaly)',
            'KNN (Logistics Delays)',
            'KMeans (RFM Clusters)'
        ]
    },
    {
        'title': 'Database (MongoDB Store)',
        'x': 19.5, 'y': 3, 'w': 28, 'h': 42,
        'bullets': [
            'Orders, Products, Clients',
            'Foreign Keys (Insight)',
            'Embedded OrderLines',
            'BSON Document Indexes'
        ]
    },
    {
        'title': 'AI Chatbot & Security',
        'x': 52.5, 'y': 3, 'w': 28, 'h': 42,
        'bullets': [
            'Ollama (Qwen2.5-7B) LLM',
            'ReAct Agent RAG Queries',
            'Biometric 2FA (ArcFace)',
            'Auto Supplier Email'
        ]
    }
]

def draw_large_font_box(ax, c):
    x, y, w, h = c['x'], c['y'], c['w'], c['h']

    # Clean box frame with solid white fill and slate border
    box = patches.FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.2,rounding_size=0.4",
        ec='#CBD5E1', fc='#FFFFFF', lw=1.5, zorder=2
    )
    ax.add_patch(box)

    # Box Title (Large Font 13.5pt Bold)
    ax.text(x + w/2, y + h - 5.0, c['title'],
            ha='center', va='center', fontsize=13.5, fontweight='bold', color='#0F172A', zorder=3)

    # Separator Line
    ax.plot([x + 2, x + w - 2], [y + h - 9.0, y + h - 9.0], color='#E2E8F0', lw=1.2, zorder=3)

    # Bullets (Large Font 11.2pt Semibold)
    line_y = y + h - 13.8
    for b in c['bullets']:
        ax.text(x + 2.2, line_y, f"•  {b}", ha='left', va='center', fontsize=11.2, fontweight='semibold', color='#334155', zorder=3)
        line_y -= 7.2

for c in components:
    draw_large_font_box(ax, c)

def draw_large_label_line(ax, p1, p2, label=""):
    ax.annotate('', xy=p2, xytext=p1,
                arrowprops=dict(arrowstyle='<->', color='#475569', lw=1.8), zorder=1)
    if label:
        mid_x = (p1[0] + p2[0]) / 2
        mid_y = (p1[1] + p2[1]) / 2
        # Larger Connection Label (10.0pt Bold)
        ax.text(mid_x, mid_y, label, ha='center', va='center', fontsize=10.0, fontweight='bold', color='#1E293B',
                bbox=dict(boxstyle='square,pad=0.25', fc='#FFFFFF', ec='#94A3B8', lw=1.0), zorder=4)

# Connection lines
draw_large_label_line(ax, (31, 72.5), (36, 72.5), "REST / JSON")
draw_large_label_line(ax, (64, 72.5), (69, 72.5), "In-Memory")
draw_large_label_line(ax, (48, 50), (34.5, 42), "Async Driver")
draw_large_label_line(ax, (52, 50), (65.5, 42), "RAG & 2FA")

plt.tight_layout()
out_paths = [
    "system_5box_architecture.png",
    "presentation/system_5box_architecture.png",
    "outputs/system_5box_architecture.png"
]

for path in out_paths:
    dir_name = os.path.dirname(path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    plt.savefig(path, bbox_inches='tight', transparent=True, dpi=300)
    print(f"Generated large-font transparent diagram successfully to: {path}")

plt.close()
