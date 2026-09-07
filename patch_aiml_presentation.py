import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN

# Load original template
src_path = "presentation/AI_ML - Copy.pptx"
if not os.path.exists(src_path):
    raise FileNotFoundError(f"Source template presentation not found at {src_path}")

prs = Presentation(src_path)
print(f"Loaded source template '{src_path}' with {len(prs.slides)} slides.")

# Theme Colors
BG_DARK = RGBColor(15, 23, 42)          # Deep Slate/Navy (#0F172A)
BG_WHITE = RGBColor(255, 255, 255)
CARD_BG = RGBColor(245, 243, 255)        # Slate/Purple-50 (#F5F3FF)
CARD_BORDER = RGBColor(124, 58, 237)     # Purple-600 (#7C3AED)
TEXT_TITLE = RGBColor(15, 23, 42)        # Slate-900 (#0F172A)
TEXT_BODY = RGBColor(51, 65, 85)         # Slate-700 (#334155)
TEXT_MUTED = RGBColor(100, 116, 139)     # Slate-500 (#64748B)
ACCENT_PURPLE = RGBColor(124, 58, 237)   # #7C3AED
ACCENT_DARK_PURPLE = RGBColor(91, 33, 182)# #5B21B6

def clear_slide(slide):
    for shape in list(slide.shapes):
        sp = shape._element
        sp.getparent().remove(sp)

def add_header(slide, tag_text, title_text):
    # Category Tag with generous top/left padding
    tag_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.45), Inches(11.0), Inches(0.35))
    tf_tag = tag_box.text_frame
    tf_tag.word_wrap = True
    tf_tag.margin_left = tf_tag.margin_right = tf_tag.margin_top = tf_tag.margin_bottom = Inches(0.05)
    p_tag = tf_tag.paragraphs[0]
    p_tag.text = tag_text.upper()
    p_tag.font.name = "Segoe UI"
    p_tag.font.size = Pt(11)
    p_tag.font.bold = True
    p_tag.font.color.rgb = ACCENT_PURPLE

    # Main Title with padding
    title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.82), Inches(11.7), Inches(0.85))
    tf_title = title_box.text_frame
    tf_title.word_wrap = True
    tf_title.margin_left = tf_title.margin_right = tf_title.margin_top = tf_title.margin_bottom = Inches(0.05)
    p_title = tf_title.paragraphs[0]
    p_title.text = title_text
    p_title.font.name = "Segoe UI"
    p_title.font.size = Pt(22)
    p_title.font.bold = True
    p_title.font.color.rgb = TEXT_TITLE

def add_footer(slide, slide_num_str):
    footer_box = slide.shapes.add_textbox(Inches(0.6), Inches(7.08), Inches(8.0), Inches(0.3))
    tf = footer_box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Inches(0.05)
    p = tf.paragraphs[0]
    p.text = f"{slide_num_str}  ·  Smart Supply Chain Dashboard"
    p.font.name = "Segoe UI"
    p.font.size = Pt(10)
    p.font.bold = True
    p.font.color.rgb = TEXT_MUTED

    brand_box = slide.shapes.add_textbox(Inches(10.0), Inches(7.08), Inches(2.7), Inches(0.3))
    tf_b = brand_box.text_frame
    tf_b.word_wrap = True
    tf_b.margin_left = tf_b.margin_right = tf_b.margin_top = tf_b.margin_bottom = Inches(0.05)
    p_b = tf_b.paragraphs[0]
    p_b.alignment = PP_ALIGN.RIGHT
    p_b.text = "AI & ML MASTERCLASS"
    p_b.font.name = "Segoe UI"
    p_b.font.size = Pt(10)
    p_b.font.bold = True
    p_b.font.color.rgb = TEXT_MUTED

def add_card_box(slide, left, top, width, height, title=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = CARD_BG
    shape.line.color.rgb = CARD_BORDER
    shape.line.width = Pt(1.5)

    if title:
        # Title text box inside card with clean padding
        title_box = slide.shapes.add_textbox(left + Inches(0.4), top + Inches(0.3), width - Inches(0.8), Inches(0.45))
        tf = title_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Inches(0.05)
        p = tf.paragraphs[0]
        p.text = title
        p.font.name = "Segoe UI"
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = ACCENT_DARK_PURPLE
        return left + Inches(0.4), top + Inches(0.8), width - Inches(0.8), height - Inches(0.95)

    return left + Inches(0.4), top + Inches(0.3), width - Inches(0.8), height - Inches(0.5)

def add_content_bullets(slide, left, top, width, height, bullets):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.15)
    tf.margin_right = Inches(0.15)
    tf.margin_top = Inches(0.1)
    tf.margin_bottom = Inches(0.1)

    for i, item in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()

        if isinstance(item, (tuple, list)):
            header_txt, sub_items = item
            p.text = header_txt
            p.font.name = "Segoe UI"
            p.font.size = Pt(12)
            p.font.bold = True
            p.font.color.rgb = TEXT_TITLE
            p.space_before = Pt(8)
            p.space_after = Pt(3)

            for sub in sub_items:
                p_sub = tf.add_paragraph()
                p_sub.text = sub
                p_sub.font.name = "Segoe UI"
                p_sub.font.size = Pt(10.5)
                p_sub.font.color.rgb = TEXT_BODY
                p_sub.space_before = Pt(2)
                p_sub.space_after = Pt(4)
        else:
            p.text = item
            p.font.name = "Segoe UI"
            p.font.size = Pt(11)
            p.font.color.rgb = TEXT_BODY
            p.space_before = Pt(4)
            p.space_after = Pt(6)

def add_picture_frame(slide, img_path, left, top, width, height):
    if not os.path.exists(img_path):
        print(f"Warning: Image '{img_path}' not found!")
        return

    frame = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    frame.fill.solid()
    frame.fill.fore_color.rgb = CARD_BG
    frame.line.color.rgb = CARD_BORDER
    frame.line.width = Pt(1.5)

    pad = Inches(0.1)
    slide.shapes.add_picture(img_path, left + pad, top + pad, width - (pad * 2), height - (pad * 2))

# ==============================================================================
# 1. SLIDE 1 (TITLE SLIDE): Dark Slate Background with Padding
# ==============================================================================
slide1 = prs.slides[0]
clear_slide(slide1)

bg_rect = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
bg_rect.fill.solid()
bg_rect.fill.fore_color.rgb = BG_DARK
bg_rect.line.fill.background()

t_box = slide1.shapes.add_textbox(Inches(1.0), Inches(1.8), Inches(11.333), Inches(4.5))
tf1 = t_box.text_frame
tf1.word_wrap = True
tf1.margin_left = tf1.margin_right = tf1.margin_top = tf1.margin_bottom = Inches(0.2)

p1 = tf1.paragraphs[0]
p1.text = "SMART SUPPLY CHAIN DASHBOARD"
p1.font.name = "Segoe UI"
p1.font.size = Pt(38)
p1.font.bold = True
p1.font.color.rgb = RGBColor(255, 255, 255)

p2 = tf1.add_paragraph()
p2.text = "Artificial Intelligence & Machine Learning Masterclass & Case Study"
p2.font.name = "Segoe UI"
p2.font.size = Pt(20)
p2.font.bold = True
p2.font.color.rgb = ACCENT_PURPLE
p2.space_before = Pt(12)

p3 = tf1.add_paragraph()
p3.text = "A practitioner's guide to AI/ML lifecycle, NoSQL data modeling, demand forecasting, and LLM ReAct agents."
p3.font.name = "Segoe UI"
p3.font.size = Pt(13)
p3.font.color.rgb = RGBColor(203, 213, 225)
p3.space_before = Pt(16)

p4 = tf1.add_paragraph()
p4.text = "Prepared by Sabor Abderrahmane  |  AddSer Conseil & Project Presentation"
p4.font.name = "Segoe UI"
p4.font.size = Pt(14)
p4.font.bold = True
p4.font.color.rgb = RGBColor(241, 245, 249)
p4.space_before = Pt(36)

# ==============================================================================
# 2. SLIDE 2: DETAILED AGENDA — PART 1
# ==============================================================================
slide2 = prs.slides[1]
clear_slide(slide2)

add_header(slide2, "DETAILED AGENDA", "Part 1: Artificial Intelligence & Machine Learning Fundamentals")
c_l, c_t, c_w, c_h = add_card_box(slide2, Inches(0.65), Inches(1.90), Inches(12.0), Inches(4.75), "Theoretical Foundations & ML Lifecycle Roadmap")
bullets_part1 = [
    ("01. Foundations of AI / ML / DL", [
        "Demystifying nested fields (AI vs ML vs Deep Learning) and artificial neural network taxonomy.",
        "The fundamental paradigm shift: Rule-Based Logic vs. Machine Pattern Learning.",
        "Historical timeline milestones from Dartmouth 1956 to modern Transformer architectures."
    ]),
    ("02. End-to-End Machine Learning Lifecycle (Steps 1–5)", [
        "Step 1 (Framing & Data Collection): Formalizing objectives, ingestion schemas, and target variables.",
        "Step 2 (Preprocessing & Cleaning): Imputation, outlier handling, Z-score standardization, and encoding.",
        "Step 3 (Exploratory Data Analysis): Distribution audits, collinearity matrices, and red flags (leakage, imbalance).",
        "Step 4 (Model Training & Tuning): Algorithm selection, loss minimization, gradient descent, hyperparameter tuning.",
        "Step 5 (Evaluation & Generalization): K-fold cross-validation, confusion matrices, precision/recall, regression RMSE."
    ]),
    ("03. Production Reality Check & Model Failure Modes", [
        "Uncovering real-world breakdown causes: Data Drift, Historical Bias Propagation, Hallucinations, and Black-Box Interpretability."
    ])
]
add_content_bullets(slide2, c_l, c_t, c_w, c_h, bullets_part1)
add_footer(slide2, "02")

# ==============================================================================
# 3. SLIDE 3: DETAILED AGENDA — PART 2
# ==============================================================================
slide3 = prs.slides[2]
clear_slide(slide3)

add_header(slide3, "DETAILED AGENDA", "Part 2: Practical Case Study — Smart Supply Chain Dashboard")
c_l2, c_t2, c_w2, c_h2 = add_card_box(slide3, Inches(0.65), Inches(1.90), Inches(12.0), Inches(4.75), "Enterprise Application & Live System Modules Roadmap")
bullets_part2 = [
    ("04. Context, Problem Statement & Specifications (MOD350 / MOD360)", [
        "Le Besoin (The Need) vs. Ce qui a été fait (Delivered Solution): Overcoming retrospective manual spreadsheets.",
        "Defining Enterprise Specifications: MOD350 (Functional Specs), MOD360 (Technical Specs), and Development Tools."
    ]),
    ("05. System Architecture & Process Integration", [
        "High-Level System Architecture Diagram & Detailed System Stack (Angular 17, FastAPI, Motor, MongoDB).",
        "Supply Chain Inventory Process: Safety Stock (SS), Reorder Point (ROP), and Days-to-Stockout countdown."
    ]),
    ("06. Data Modeling & NoSQL Schema with Foreign Keys", [
        "MongoDB NoSQL Collections: Embedded collections (SalesOrderLine) vs. Referenced Foreign Key collections (Insight, Client, Product).",
        "Updated System UML Class Diagram with explicit Foreign Key (FK) attribute mappings."
    ]),
    ("07. Functional Telemetry Cards (Dedicated KPI Slides & Alerts)", [
        "Dedicated KPI Slides: Service Level (OTIF), Average Delivery Lead Time, Stockless Rate, and Global SC Health Score.",
        "Proactive Alert System: Real-time notification feed & Quality Issue Alert case study (Article PF13217 with 10 impacted orders).",
        "Predictive Engines & Chatbot: 90-Day Prophet/ARIMA Demand Forecast, 360° Product Insight & LightGBM Anomaly Classifier, Local ReAct LLM Chatbot (Ollama Qwen2.5-7B) & MLOps Hot-Swapping."
    ])
]
add_content_bullets(slide3, c_l2, c_t2, c_w2, c_h2, bullets_part2)
add_footer(slide3, "03")

# Remove old Slide 16 ("Thank You") from template so we append Part 2 slides cleanly
slide_layout = prs.slide_layouts[0]
for idx, slide in enumerate(prs.slides):
    for shape in slide.shapes:
        if shape.has_text_frame and "THANK YOU" in shape.text_frame.text.upper():
            rId = prs.slides._sldIdLst[idx].rId
            prs.part.drop_rel(rId)
            del prs.slides._sldIdLst[idx]
            print(f"Removed old 'Thank You' slide.")
            break

# ==============================================================================
# 4. APPEND NEW PART 2 SLIDES (SLIDES 16 TO 34)
# ==============================================================================

# Slide 16: Section 04 Divider
s16_div = prs.slides.add_slide(slide_layout)
add_header(s16_div, "SECTION 04", "Case Study: Smart Supply Chain Dashboard")
c_l, c_t, c_w, c_h = add_card_box(s16_div, Inches(0.65), Inches(1.90), Inches(12.0), Inches(4.75), "Applying ML Lifecycle & LLM Agents to Supply Chain Management")
s16_bullets = [
    ("End-to-End Decision Support System", [
        "A full-stack predictive logistics platform deployed for AddSer Conseil (clients LISI Aerospace & Hermès).",
        "Combines real-time telemetry, time-series sales forecasting, ML operational anomaly detection, and LLM chatbot intelligence."
    ]),
    ("Core Architectural Pillars", [
        "Frontend: Angular 17, RxJS, Chart.js interactive dashboards with real-time change detection.",
        "Backend: FastAPI async endpoints, Motor non-blocking driver, MongoDB NoSQL document store.",
        "AI/ML Engine: Meta Prophet for 90-day sales forecasting, LightGBM anomaly detection, KNN delay prediction, KMeans RFM client clustering.",
        "Generative AI: Ollama local LLM (Qwen2.5-7B) driving a ReAct agent for natural language database querying."
    ])
]
add_content_bullets(s16_div, c_l, c_t, c_w, c_h, s16_bullets)
add_footer(s16_div, "16")

# Slide 17: Problem Statement (Le Besoin)
s17_need = prs.slides.add_slide(slide_layout)
add_header(s17_need, "CASE STUDY: CONTEXT & NEED", "Problem Statement: The Operational Challenge (Le Besoin)")
c_l, c_t, c_w, c_h = add_card_box(s17_need, Inches(0.65), Inches(1.90), Inches(12.0), Inches(4.75), "Supply Chain Bottlenecks & Legacy Friction")
s17_bullets = [
    ("Retrospective Reporting & Fragmented Spreadsheets", [
        "Traditional supply chain operations rely on manual Excel files and static monthly reports, creating data silos.",
        "Decision-makers lack real-time visibility into active stockout risks and vendor delivery delays before disruptions occur."
    ]),
    ("Stockout Vulnerability & Revenue Loss", [
        "Without predictive demand forecasting, high customer demand spikes lead to unmanaged stockouts and lost revenue.",
        "Lack of dynamic Safety Stock and Reorder Point calculations causes either overstocking or stock exhaustion."
    ]),
    ("Lack of Automated Incident Detection", [
        "Manual fraud and delay verification requires hours of manual cross-referencing across thousands of transactions.",
        "Logistics managers require an automated, predictive platform providing real-time telemetry and instant alert feeds."
    ])
]
add_content_bullets(s17_need, c_l, c_t, c_w, c_h, s17_bullets)
add_footer(s17_need, "17")

# Slide 18: Delivered Solution & Specifications (Ce qui a été fait - MOD Specs & Tools)
s18_sol = prs.slides.add_slide(slide_layout)
add_header(s18_sol, "CASE STUDY: DELIVERED SOLUTION", "Enterprise Specifications (MOD350 / MOD360 & Dev Tools)")
c_l, c_t, c_w, c_h = add_card_box(s18_sol, Inches(0.65), Inches(1.90), Inches(5.8), Inches(4.75), "Defining Enterprise MOD Specifications")
s18_bullets_1 = [
    ("What is a MOD in Enterprise Methodology?", [
        "MOD (Modification / Specification Document) is the standard SAP/ERP project methodology for defining functional and technical scope."
    ]),
    ("MOD350 — Functional Specifications", [
        "Ergonomic UI control panel & live telemetry cards (OTIF, SC Health Score, Stockless Rate).",
        "90-Day Prophet demand forecast & interactive sales calendar.",
        "Proactive alert feed, 360° SKU insight modal, and conversational ReAct AI assistant."
    ])
]
add_content_bullets(s18_sol, c_l, c_t, c_w, c_h, s18_bullets_1)

c_l2, c_t2, c_w2, c_h2 = add_card_box(s18_sol, Inches(6.88), Inches(1.90), Inches(5.8), Inches(4.75), "MOD360 & Development Stack")
s18_bullets_2 = [
    ("MOD360 — Technical Specifications", [
        "Angular 17 SPA with RxJS reactive state streams.",
        "FastAPI async REST framework with Motor driver for non-blocking MongoDB queries.",
        "Biometric 2FA (InsightFace ArcFace 512D embeddings) & zero-downtime hot-swapping."
    ]),
    ("Development Tools & Infrastructure", [
        "Python 3.12, TypeScript, Angular CLI, Node.js.",
        "MongoDB Enterprise NoSQL, Ollama Local LLM (Qwen2.5-7B).",
        "VS Code, Git version control, Chart.js, FullCalendar."
    ])
]
add_content_bullets(s18_sol, c_l2, c_t2, c_w2, c_h2, s18_bullets_2)
add_footer(s18_sol, "18")

# Slide 19: High-Level System Architecture Diagram
s19_5box = prs.slides.add_slide(slide_layout)
add_header(s19_5box, "CASE STUDY: ARCHITECTURE OVERVIEW", "High-Level System Architecture Diagram (MOD360)")
add_picture_frame(s19_5box, "system_5box_architecture.png", Inches(0.65), Inches(1.85), Inches(12.0), Inches(4.9))
add_footer(s19_5box, "19")

# Slide 20: Detailed Technical Stack & Layering Image
s20_arch = prs.slides.add_slide(slide_layout)
add_header(s20_arch, "CASE STUDY: DETAILED ARCHITECTURE", "Detailed System Stack & Component Interconnections")
c_l, c_t, c_w, c_h = add_card_box(s20_arch, Inches(0.65), Inches(1.90), Inches(5.8), Inches(4.75), "Layered Technical Stack")
s20_bullets = [
    ("Frontend Layer (Client SPA)", [
        "Angular 17, TypeScript, RxJS for asynchronous reactive state streams.",
        "Chart.js interactive plots & FullCalendar operational scheduling."
    ]),
    ("Backend REST API Layer", [
        "FastAPI asynchronous framework with Motor MongoDB driver.",
        "Pydantic strict schema validation on all incoming payload routes."
    ]),
    ("Intelligence & Storage Layer", [
        "MongoDB NoSQL document store (Orders, Products, Clients, Suppliers).",
        "Meta Prophet & ARIMA for 90-day time-series demand forecasting.",
        "Ollama (Qwen2.5) local LLM driving ReAct natural language database querying."
    ])
]
add_content_bullets(s20_arch, c_l, c_t, c_w, c_h, s20_bullets)
add_picture_frame(s20_arch, "images for mod350/system_structure.png", Inches(6.88), Inches(1.90), Inches(5.8), Inches(4.75))
add_footer(s20_arch, "20")

# Slide 21: Supply Chain Inventory Process & ROP/SS Formulations
s21_inv = prs.slides.add_slide(slide_layout)
add_header(s21_inv, "CASE STUDY: INVENTORY PROCESS", "Inventory Process, Safety Stock & Reorder Point (ROP)")
c_l, c_t, c_w, c_h = add_card_box(s21_inv, Inches(0.65), Inches(1.90), Inches(5.8), Inches(4.75), "Safety Stock & ROP Formulations")
s21_bullets = [
    ("Safety Stock (SS) Formulation", [
        "SS = max(15, round(Z * std_demand * sqrt(Lead_Time))) where Z = 1.65 (95% service level).",
        "Buffers against lead time volatility and unexpected customer demand spikes."
    ]),
    ("Reorder Point (ROP) Calculation", [
        "ROP = round(SS + Average Daily Demand * Lead Time).",
        "Automated replenishment trigger: when physical stock <= ROP, draft Purchase Orders are generated."
    ]),
    ("Days to Stockout Countdown", [
        "Days to Stockout = Current Stock / Predicted Daily Demand.",
        "Provides logistics managers with exact countdown days before inventory exhaustion."
    ])
]
add_content_bullets(s21_inv, c_l, c_t, c_w, c_h, s21_bullets)
add_picture_frame(s21_inv, "images for mod350/AI Supply Chain Dashboard inventory.png", Inches(6.88), Inches(1.90), Inches(5.8), Inches(4.75))
add_footer(s21_inv, "21")

# ==============================================================================
# DEDICATED KPI SLIDES (DYNAMICALLY CONFIGURABLE TARGET THRESHOLDS)
# ==============================================================================

# Slide 22: DEDICATED KPI 1 — SERVICE LEVEL (OTIF)
s22_otif = prs.slides.add_slide(slide_layout)
add_header(s22_otif, "EXECUTIVE TELEMETRY: KPI 1", "Service Level (OTIF - On Time In Full)")
c_l, c_t, c_w, c_h = add_card_box(s22_otif, Inches(0.65), Inches(1.90), Inches(12.0), Inches(4.75), "Real-Time Tracking of On-Time & Complete Fulfillments")
s22_otif_bullets = [
    ("Core Definition & Operational Meaning", [
        "Service Level (OTIF): Real-time tracking of On-Time In-Full order fulfillments.",
        "Evaluates the percentage of customer sales orders delivered strictly on schedule and without partial quantities."
    ]),
    ("Formula & Configurable Thresholds", [
        "Formula: OTIF (%) = (Number of On-Time & In-Full Orders / Total Shipped Orders) * 100",
        "Dynamic Thresholds: Evaluates real-time OTIF percentage against user-defined target thresholds (Green - Target Met | Yellow - Warning | Red - Critical Breach)."
    ]),
    ("Historical Evolution & Baseline Comparison", [
        "Compares live telemetry against previous month baseline (Value M-1) to evaluate service reliability trends over time."
    ])
]
add_content_bullets(s22_otif, c_l, c_t, c_w, c_h, s22_otif_bullets)
add_footer(s22_otif, "22")

# Slide 23: DEDICATED KPI 2 — AVERAGE DELIVERY LEAD TIME
s23_lt = prs.slides.add_slide(slide_layout)
add_header(s23_lt, "EXECUTIVE TELEMETRY: KPI 2", "Average Delivery Lead Time & Transit Gap")
c_l, c_t, c_w, c_h = add_card_box(s23_lt, Inches(0.65), Inches(1.90), Inches(12.0), Inches(4.75), "Tracking Delivery Schedule Deltas & Partner Transit Latency")
s23_lt_bullets = [
    ("Core Definition & Operational Meaning", [
        "Average Delivery Lead Time: Ecart entre le delai de livraison souhaitee et le delai de livraison reele.",
        "Measures the gap between the promised target delivery date and the actual real-world delivery timestamp."
    ]),
    ("Formula & Configurable Thresholds", [
        "Formula: Delivery Lead Time Gap = Actual Delivery Date - Promised Target Delivery Date",
        "Dynamic Thresholds: Evaluates transit lead time gap against user-defined tolerance thresholds (Green - Within Target | Yellow - Warning | Red - Delay Risk)."
    ]),
    ("Carrier Performance & Trend Tracking", [
        "Identifies partner transport bottlenecks and compares lead time deltas against previous month baseline (Value M-1)."
    ])
]
add_content_bullets(s23_lt, c_l, c_t, c_w, c_h, s23_lt_bullets)
add_footer(s23_lt, "23")

# Slide 24: DEDICATED KPI 3 — STOCKLESS RATE
s24_stk = prs.slides.add_slide(slide_layout)
add_header(s24_stk, "EXECUTIVE TELEMETRY: KPI 3", "Stockless Rate (Catalogue Product Unavailability)")
c_l, c_t, c_w, c_h = add_card_box(s24_stk, Inches(0.65), Inches(1.90), Inches(12.0), Inches(4.75), "Catalogue Stock Exhaustion & Customer Demand Exposure")
s24_stk_bullets = [
    ("Core Definition & Operational Meaning", [
        "Stockless Rate: Percentage of catalogue products currently out of stock when active customer demand occurs.",
        "Google Summary Definition: The stockless rate measures how often active products are unavailable when customers want to buy them."
    ]),
    ("Formula & Configurable Thresholds", [
        "Formula: Stockless Rate (%) = (Active SKUs Out of Stock / Total Active Catalogue SKUs) * 100",
        "Dynamic Thresholds: Tracks catalogue stock exhaustion against user-defined stockout limits (Green - Optimal Availability | Yellow - Warning | Red - Critical Stockout)."
    ]),
    ("Demand Impact & Automated Safety Triggers", [
        "Directly quantifies lost sales revenue exposure and triggers automatic Safety Stock & ROP replenishment orders."
    ])
]
add_content_bullets(s24_stk, c_l, c_t, c_w, c_h, s24_stk_bullets)
add_footer(s24_stk, "24")

# Slide 25: DEDICATED KPI 4 — GLOBAL SC HEALTH SCORE
s25_hs = prs.slides.add_slide(slide_layout)
add_header(s25_hs, "EXECUTIVE TELEMETRY: KPI 4", "Global Supply Chain Health Score (SC Health Score)")
c_l, c_t, c_w, c_h = add_card_box(s25_hs, Inches(0.65), Inches(1.90), Inches(12.0), Inches(4.75), "Synthetic Composite Index for Executive Decision Support")
s25_hs_bullets = [
    ("Core Definition & Operational Meaning", [
        "Global SC Health Score: Synthetic metric combining OTIF service level and stockless rates regarding outstanding orders.",
        "Synthesizes fulfillment completeness, product availability, and lead time latency into a single 0 to 100 composite index."
    ]),
    ("Formula & Configurable Thresholds", [
        "Formula: SC Health Score = (Weight 1 * OTIF) + (Weight 2 * (100 - Stockless Rate)) + (Weight 3 * (100 - Lead Time Gap Index))",
        "Dynamic Thresholds: Calculates composite operational health against user-defined target scores (Green - Healthy Pipeline | Yellow - Moderate Risk | Red - Critical Risk)."
    ]),
    ("Executive Value & Baseline Evolution", [
        "Provides executive decision-makers with an instant 360-degree health rating and month-over-month trend deltas (Value M-1)."
    ])
]
add_content_bullets(s25_hs, c_l, c_t, c_w, c_h, s25_hs_bullets)
add_footer(s25_hs, "25")

# Slide 26: DEDICATED MODULE — LIVE NOTIFICATION FEED & INCIDENT ALERTS
s26_alr = prs.slides.add_slide(slide_layout)
add_header(s26_alr, "PROACTIVE ALERTS", "Live Notification Feed & Change Detection")
c_l, c_t, c_w, c_h = add_card_box(s26_alr, Inches(0.65), Inches(1.90), Inches(12.0), Inches(4.75), "Automated Event Monitoring & Incident Case Study")
s26_alr_bullets = [
    ("Priority Alert Feed & Dynamic UI Sync", [
        "Priority alert feed flagging anomaly risks, inventory shortages, and logistics delays.",
        "Background state sync triggering dynamic UI re-rendering without manual refresh."
    ]),
    ("Concrete Incident Example: Quality Issue Alert", [
        "Alert Type: Quality Issue / Batch Defect Alert",
        "Affected SKU: Article PF13217 (High-Precision Component)",
        "Impacted Orders List: First 10 concerned customers / orders (Orders #1001 to #1010)",
        "Automated System Action: Instant quarantine flag placed on SKU PF13217 inventory batch and alert email sent to account managers."
    ])
]
add_content_bullets(s26_alr, c_l, c_t, c_w, c_h, s26_alr_bullets)
add_footer(s26_alr, "26")

# Slide 27: Data Modeling & Foreign Keys vs Embedded Collections
s27_data = prs.slides.add_slide(slide_layout)
add_header(s27_data, "CASE STUDY: DATA MODELING", "MongoDB NoSQL Architecture: Foreign Keys & Embedded Collections")
c_l, c_t, c_w, c_h = add_card_box(s27_data, Inches(0.65), Inches(1.90), Inches(12.0), Inches(4.75), "NoSQL Document Schema Design Principles")
s27_data_bullets = [
    ("Foreign Key References in NoSQL (Insight & Order Collections)", [
        "Even though MongoDB is a NoSQL document database, explicit relational Foreign Keys (DBRefs / ObjectId links) are maintained.",
        "The Insight collection explicitly stores FKs: order_id, client_id, product_sku to maintain relational integrity across AI telemetry.",
        "Enables multi-collection join queries required for ReAct LLM database interaction."
    ]),
    ("Embedded Collections vs. Referenced Collections (Yasmine's Architecture Recommendation)", [
        "Embedded Document Pattern: High-speed, atomic collections like SalesOrderLine are embedded directly inside SalesOrder document arrays for 1-click retrieval.",
        "Referenced Collection Pattern: Entities with independent lifecycles (Client, Product, Insight, Anomaly) use Foreign Keys to prevent redundant data duplication and ensure global consistency."
    ])
]
add_content_bullets(s27_data, c_l, c_t, c_w, c_h, s27_data_bullets)
add_footer(s27_data, "27")

# Slide 28: System UML Class Diagram
s28_uml = prs.slides.add_slide(slide_layout)
add_header(s28_uml, "CASE STUDY: CLASS DIAGRAM", "System UML Class Diagram")
add_picture_frame(s28_uml, "class_diagram_latest.png", Inches(0.65), Inches(1.85), Inches(12.0), Inches(4.9))
add_footer(s28_uml, "28")

# Slide 29: Demand Forecasting Engine (Meta Prophet & ARIMA)
s29_fore = prs.slides.add_slide(slide_layout)
add_header(s29_fore, "CASE STUDY: FORECASTING", "Demand Forecasting Engine (Meta Prophet & ARIMA)")
c_l, c_t, c_w, c_h = add_card_box(s29_fore, Inches(0.65), Inches(1.90), Inches(5.8), Inches(4.75), "Predictive Demand Modeling")
s29_bullets = [
    ("Time-Series Demand Modeling", [
        "Meta Prophet model projecting daily demand across a 90-day horizon with 95% confidence bounds.",
        "Logarithmic variance transformation log(1+y) to stabilize highly volatile sales trends.",
        "Seasonal ARIMA (1,1,1)x(1,0,1)_7 engine with Gaussian noise simulation N(0, sigma^2)."
    ]),
    ("Visual Sales Calendar & Stress Simulator", [
        "Displays predicted daily demand directly on an interactive FullCalendar view.",
        "Simulates impact of sudden bulk orders on physical warehouse inventory."
    ])
]
add_content_bullets(s29_fore, c_l, c_t, c_w, c_h, s29_bullets)
add_picture_frame(s29_fore, "images for mod350/AI Supply Chain Dashboard demand forecasting.png", Inches(6.88), Inches(1.90), Inches(5.8), Inches(4.75))
add_footer(s29_fore, "29")

# Slide 30: Automated Reordering & Supplier Reliability
s30_pur = prs.slides.add_slide(slide_layout)
add_header(s30_pur, "CASE STUDY: PURCHASES", "Automated Reordering & Supplier Reliability")
c_l, c_t, c_w, c_h = add_card_box(s30_pur, Inches(0.65), Inches(1.90), Inches(5.8), Inches(4.75), "Supplier Scoring & Replenishment")
s30_bullets = [
    ("Automated Purchase Orders", [
        "Automatic draft PO generation when SKU stock breaches the Reorder Point.",
        "Calculates recommended order quantities (EOQ) based on supplier lead times."
    ]),
    ("Supplier Reliability Matrix", [
        "Evaluates vendor OTIF delivery compliance and historical delay risk.",
        "Identifies critical supplier bottlenecks to mitigate procurement delays."
    ])
]
add_content_bullets(s30_pur, c_l, c_t, c_w, c_h, s30_bullets)
add_picture_frame(s30_pur, "images for mod350/AI Supply Chain Dashboard purchases.png", Inches(6.88), Inches(1.90), Inches(5.8), Inches(4.75))
add_footer(s30_pur, "30")

# Slide 31: 360° SKU Analytics & LightGBM Anomaly Classifier
s31_prod = prs.slides.add_slide(slide_layout)
add_header(s31_prod, "CASE STUDY: PRODUCT ANALYTICS", "360° SKU Analytics & LightGBM Anomaly Classifier")
c_l, c_t, c_w, c_h = add_card_box(s31_prod, Inches(0.65), Inches(1.90), Inches(5.8), Inches(4.75), "Granular SKU-Level Intelligence")
s31_bullets = [
    ("360° Product Insight Modal", [
        "Detailed product analytics panel accessible directly from dashboard cards.",
        "Price & discount elasticity analysis evaluating profit margin impacts."
    ]),
    ("LightGBM Anomaly Detection & Human Verdict", [
        "Classifies sales order attributes to flag fraudulent or irregular orders upon ingestion.",
        "Provides explicit human-in-the-loop verdict overrides for final decision making."
    ])
]
add_content_bullets(s31_prod, c_l, c_t, c_w, c_h, s31_bullets)
add_picture_frame(s31_prod, "images for mod350/Product insight details pop up.png", Inches(6.88), Inches(1.90), Inches(5.8), Inches(4.75))
add_footer(s31_prod, "31")

# Slide 32: Conversational AI Chatbot (ReAct LLM & Ollama)
s32_chat = prs.slides.add_slide(slide_layout)
add_header(s32_chat, "CASE STUDY: AI CHATBOT", "Conversational DB Assistant (ReAct & Ollama)")
c_l, c_t, c_w, c_h = add_card_box(s32_chat, Inches(0.65), Inches(1.90), Inches(5.8), Inches(4.75), "Natural Language Database Querying")
s32_bullets = [
    ("ReAct Agent Architecture", [
        "Translates natural language user questions into structured MongoDB queries.",
        "Runs 100% locally via Ollama (Qwen2.5-7B) ensuring full enterprise data privacy."
    ]),
    ("Multi-Collection RAG Resolution & Emailing", [
        "Resolves relational context across Orders -> Products -> Purchases -> Suppliers.",
        "Generates automated reminder emails and triggers asynchronous SMTP dispatch to vendors."
    ])
]
add_content_bullets(s32_chat, c_l, c_t, c_w, c_h, s32_bullets)
add_picture_frame(s32_chat, "images for mod350/Ai chatbot pop up.png", Inches(6.88), Inches(1.90), Inches(5.8), Inches(4.75))
add_footer(s32_chat, "32")

# Slide 33: MLOps Pipelines & Zero-Downtime Hot-Swapping
s33_mlops = prs.slides.add_slide(slide_layout)
add_header(s33_mlops, "CASE STUDY: MLOPS & ML ENGINES", "Data Pipelines & Zero-Downtime Hot-Swapping")
c_l, c_t, c_w, c_h = add_card_box(s33_mlops, Inches(0.65), Inches(1.90), Inches(5.8), Inches(4.75), "Pipeline Architecture & Hot-Swapping")
s33_bullets_1 = [
    ("Batch Ingestion & Async Retraining", [
        "Supports CSV/XLSX file uploads with automated Pandas schema validation.",
        "Asyncio OS subprocesses handle background model retraining without blocking FastAPI."
    ]),
    ("Zero-Downtime Hot-Swapping", [
        "In-memory atomic model pointer replacement ensures 24/7 API availability."
    ])
]
add_content_bullets(s33_mlops, c_l, c_t, c_w, c_h, s33_bullets_1)

c_l2, c_t2, c_w2, c_h2 = add_card_box(s33_mlops, Inches(6.88), Inches(1.90), Inches(5.8), Inches(4.75), "Integrated Machine Learning Models")
s33_bullets_2 = [
    ("LightGBM (Anomaly Classifier)", [
        "Flags fraudulent or irregular sales orders in real-time upon data ingestion."
    ]),
    ("KNN (Logistics Delay Predictor)", [
        "Predicts delivery transit delays based on historical shipping modes and lead time deltas."
    ]),
    ("KMeans (RFM Customer & Supplier Segmentation)", [
        "Clusters clients into Champions, Loyal, At Risk segments to guide inventory allocation."
    ])
]
add_content_bullets(s33_mlops, c_l2, c_t2, c_w2, c_h2, s33_bullets_2)
add_footer(s33_mlops, "33")

# Slide 34: Conclusion & Q&A Slide
s34_end = prs.slides.add_slide(slide_layout)
bg_end = s34_end.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
bg_end.fill.solid()
bg_end.fill.fore_color.rgb = BG_DARK
bg_end.line.fill.background()

thank_box = s34_end.shapes.add_textbox(Inches(1.0), Inches(2.5), Inches(11.333), Inches(3.0))
tf_t = thank_box.text_frame
tf_t.word_wrap = True
p_t = tf_t.paragraphs[0]
p_t.alignment = PP_ALIGN.CENTER
p_t.text = "Thank you for your attention."
p_t.font.name = "Segoe UI"
p_t.font.size = Pt(36)
p_t.font.bold = True
p_t.font.color.rgb = RGBColor(255, 255, 255)

sub_t = tf_t.add_paragraph()
sub_t.alignment = PP_ALIGN.CENTER
sub_t.text = "Sabor Abderrahmane  |  Smart Supply Chain Dashboard Case Study"
sub_t.font.name = "Segoe UI"
sub_t.font.size = Pt(18)
sub_t.font.bold = True
sub_t.font.color.rgb = ACCENT_PURPLE
sub_t.space_before = Pt(15)

sub_t2 = tf_t.add_paragraph()
sub_t2.alignment = PP_ALIGN.CENTER
sub_t2.text = "Questions & Interactive System Demonstration"
sub_t2.font.name = "Segoe UI"
sub_t2.font.size = Pt(14)
sub_t2.font.color.rgb = RGBColor(203, 213, 225)
sub_t2.space_before = Pt(10)

# Save updated presentation
output_paths = [
    "presentation/AI_ML.pptx",
    "outputs/AI_ML.pptx"
]

for out_path in output_paths:
    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        prs.save(out_path)
        print(f"Successfully generated and saved presentation to: {out_path}")
    except PermissionError:
        print(f"Notice: Could not overwrite {out_path} (file is locked/open).")
        alt_path = out_path.replace(".pptx", "_Updated.pptx")
        prs.save(alt_path)
        print(f"Saved updated copy to: {alt_path}")
    except Exception as e:
        print(f"Error saving to {out_path}: {e}")

print(f"Total slides in updated presentation: {len(prs.slides)}")
