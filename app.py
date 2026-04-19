import streamlit as st
import streamlit.components.v1 as components
import anthropic
import json
import os
import re
from notifications import register_lead


def _md_inline(text: str) -> str:
    """Inline markdown: bold, italic, code."""
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'<em>\1</em>', text)
    text = re.sub(
        r'`([^`]+?)`',
        r'<code style="background:rgba(178,172,136,0.15);padding:1px 6px;'
        r'border-radius:4px;font-family:monospace;font-size:0.88em;">\1</code>',
        text,
    )
    return text


def md_to_html(text: str) -> str:
    """Convert Claude markdown to HTML for rendering inside unsafe_allow_html divs."""
    H2 = 'color:#B2AC88;font-size:1.1rem;font-weight:700;margin:1.1rem 0 0.4rem;'
    H3 = 'color:#B2AC88;font-size:1rem;font-weight:700;margin:0.9rem 0 0.3rem;'
    LI = 'margin:2px 0;'

    lines = text.split('\n')
    out = []
    in_ul = in_ol = False

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            out.append('</ul>')
            in_ul = False
        if in_ol:
            out.append('</ol>')
            in_ol = False

    for line in lines:
        s = line.strip()

        if s.startswith('### '):
            close_lists()
            out.append(f'<h3 style="{H3}">{_md_inline(s[4:])}</h3>')
        elif s.startswith('## '):
            close_lists()
            out.append(f'<h2 style="{H2}">{_md_inline(s[3:])}</h2>')
        elif s.startswith('# '):
            close_lists()
            out.append(f'<h2 style="{H2}">{_md_inline(s[2:])}</h2>')
        elif s.startswith('- ') or s.startswith('* '):
            if in_ol:
                out.append('</ol>')
                in_ol = False
            if not in_ul:
                out.append('<ul style="margin:0.4rem 0;padding-left:1.4rem;">')
                in_ul = True
            out.append(f'<li style="{LI}">{_md_inline(s[2:])}</li>')
        elif re.match(r'^\d+\.\s', s):
            if in_ul:
                out.append('</ul>')
                in_ul = False
            if not in_ol:
                out.append('<ol style="margin:0.4rem 0;padding-left:1.4rem;">')
                in_ol = True
            out.append(f'<li style="{LI}">{_md_inline(re.sub(r"^\d+\.\s", "", s))}</li>')
        elif s in ('---', '***', '___'):
            close_lists()
            out.append('<hr style="border-color:#333;margin:0.8rem 0;">')
        elif s == '':
            close_lists()
            out.append('<div style="height:0.4rem;"></div>')
        else:
            close_lists()
            out.append(f'<p style="margin:0.2rem 0;">{_md_inline(s)}</p>')

    close_lists()
    return '\n'.join(out)

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Rigged Game Breaker",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  /* Root Variables */
  :root {
    --bg-primary: #1E1E1E;
    --bg-card: #252525;
    --bg-card-hover: #2C2C2C;
    --accent: #B2AC88;
    --accent-dim: #8C8770;
    --text-primary: #F0EDE6;
    --text-secondary: #9E9A8E;
    --border: #333333;
    --success: #6B9E78;
    --radius: 15px;
  }

  /* Global */
  html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background-color: var(--bg-primary) !important;
    color: var(--text-primary) !important;
  }
  .main { background-color: var(--bg-primary) !important; }
  .block-container { padding-top: 4.2rem !important; padding-bottom: 2rem; }

  /* Hide sidebar entirely */
  [data-testid="stSidebar"],
  [data-testid="stSidebarCollapsedControl"] { display: none !important; }

  /* Cards */
  .card {
    background: var(--bg-card);
    border-radius: var(--radius);
    padding: 1.5rem;
    border: 1px solid var(--border);
    margin-bottom: 1rem;
    transition: border-color 0.2s ease;
  }
  .card:hover { border-color: var(--accent-dim); }

  /* Hero Header */
  .hero-header {
    background: linear-gradient(135deg, #1E1E1E 0%, #252520 50%, #1E1E1E 100%);
    border-radius: var(--radius);
    padding: 2.5rem;
    border: 1px solid var(--accent-dim);
    margin-bottom: 2rem;
    text-align: center;
  }
  .hero-header h1 {
    color: var(--accent) !important;
    font-size: 2.2rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.5px !important;
    margin-bottom: 0.5rem !important;
  }
  .hero-header p {
    color: var(--text-secondary) !important;
    font-size: 1.05rem !important;
    font-style: italic !important;
    margin: 0 !important;
  }

  /* Section Titles */
  .section-title {
    color: var(--accent) !important;
    font-size: 1.4rem !important;
    font-weight: 600 !important;
    border-bottom: 2px solid var(--accent-dim);
    padding-bottom: 0.4rem;
    margin-bottom: 1.2rem;
  }

  /* Diagnosis Tag */
  .tag {
    display: inline-block;
    background: rgba(178,172,136,0.15);
    color: var(--accent);
    border: 1px solid var(--accent-dim);
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    margin-right: 6px;
  }

  /* Progress Bar Override */
  .stProgress > div > div { background-color: var(--accent) !important; }
  .stProgress > div { background-color: var(--border) !important; border-radius: 10px; }

  /* Buttons */
  .stButton > button {
    background-color: var(--accent) !important;
    color: #1E1E1E !important;
    font-weight: 600 !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.5rem 1.5rem !important;
    transition: all 0.2s ease !important;
  }
  .stButton > button:hover {
    background-color: #C8C3A0 !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(178,172,136,0.3) !important;
  }

  /* Text Inputs */
  .stTextInput > div > div > input,
  .stTextArea > div > div > textarea {
    background-color: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-primary) !important;
    border-radius: 10px !important;
  }
  .stTextInput > div > div > input:focus,
  .stTextArea > div > div > textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px rgba(178,172,136,0.2) !important;
  }

  /* Sliders */
  .stSlider > div > div > div > div { background-color: var(--accent) !important; }

  /* Number Input */
  .stNumberInput > div > div > input {
    background-color: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-primary) !important;
    border-radius: 10px !important;
  }

  /* Expanders */
  .stExpander {
    background-color: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
  }
  .stExpander > div > div > div > div > p {
    color: var(--text-primary) !important;
  }

  /* Select Box */
  .stSelectbox > div > div {
    background-color: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
  }

  /* Chat Messages */
  .chat-user {
    background: rgba(178,172,136,0.08);
    border-left: 3px solid var(--accent);
    border-radius: 0 12px 12px 0;
    padding: 0.8rem 1rem;
    margin: 0.5rem 0;
    color: var(--text-primary) !important;
  }
  .chat-ai {
    background: var(--bg-card);
    border-left: 3px solid #4A7A57;
    border-radius: 0 12px 12px 0;
    padding: 0.8rem 1rem;
    margin: 0.5rem 0;
    color: var(--text-primary) !important;
  }
  .chat-label {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
    color: var(--accent) !important;
  }

  /* Metric Cards */
  .metric-card {
    background: var(--bg-card);
    border-radius: var(--radius);
    padding: 1.2rem 1.5rem;
    border: 1px solid var(--border);
    text-align: center;
  }
  .metric-value {
    font-size: 2rem;
    font-weight: 700;
    color: var(--accent);
  }
  .metric-label {
    font-size: 0.8rem;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  /* Bundle CTA */
  .bundle-card {
    background: linear-gradient(135deg, #252520, #1E1E18);
    border-radius: var(--radius);
    padding: 1.2rem;
    border: 1px solid var(--accent-dim);
    text-align: center;
  }
  .bundle-price {
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--accent);
  }

  /* Recipe Badge */
  .recipe-badge {
    display: inline-block;
    background: rgba(178,172,136,0.12);
    color: var(--accent);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-weight: 600;
    margin: 2px;
  }

  /* Gate Card */
  .gate-card {
    background: var(--bg-card);
    border-radius: var(--radius);
    padding: 2rem;
    border: 1px solid var(--accent-dim);
    max-width: 480px;
    margin: 2rem auto;
    text-align: center;
  }

  /* Info Box */
  .info-box {
    background: rgba(178,172,136,0.07);
    border-radius: 10px;
    padding: 0.8rem 1rem;
    border-left: 3px solid var(--accent-dim);
    margin-bottom: 0.8rem;
    color: var(--text-secondary) !important;
    font-size: 0.9rem;
  }

  /* Divider */
  hr { border-color: var(--border) !important; margin: 1.5rem 0 !important; }

  /* Hide Streamlit Branding */
  #MainMenu, footer, header { visibility: hidden; }

  /* Alert */
  .stAlert { border-radius: var(--radius) !important; }

  /* ── Radio nav hidden off-screen (used only as state trigger) ── */
  div[data-testid="stRadio"] {
    position: fixed !important;
    top: -9999px !important;
    left: -9999px !important;
    opacity: 0 !important;
    pointer-events: none !important;
  }

  /* ── Mobile Responsive ── */
  @media (max-width: 768px) {
    .block-container {
      padding-left: 0.8rem !important;
      padding-right: 0.8rem !important;
      padding-top: 0.8rem !important;
      padding-bottom: 5rem !important;
    }
    .hero-header {
      padding: 1.4rem 1rem !important;
      margin-bottom: 1.2rem !important;
    }
    .hero-header h1 {
      font-size: 1.5rem !important;
      letter-spacing: 0 !important;
    }
    .hero-header p { font-size: 0.9rem !important; }
    .gate-card {
      padding: 1.4rem 1rem !important;
      max-width: 100% !important;
    }
    .card { padding: 1rem !important; }
    .info-box {
      font-size: 0.82rem !important;
      padding: 0.7rem 0.9rem !important;
    }
    .metric-card {
      padding: 0.8rem 0.5rem !important;
    }
    .metric-value { font-size: 1.4rem !important; }
    .metric-label { font-size: 0.7rem !important; }
    .section-title {
      font-size: 1.1rem !important;
    }
    .chat-user, .chat-ai {
      padding: 0.6rem 0.8rem !important;
      font-size: 0.88rem !important;
      margin: 0.3rem 0 !important;
    }
    .bundle-card { padding: 0.9rem !important; }
    .bundle-price { font-size: 1.4rem !important; }
    .tag { font-size: 0.68rem !important; padding: 2px 8px !important; }
  }

  @media (max-width: 480px) {
    .hero-header h1 { font-size: 1.25rem !important; }
    .hero-header p { font-size: 0.82rem !important; }
    .stat-value { font-size: 1.6rem !important; }
    .recipe-badge { font-size: 0.65rem !important; }
  }
</style>
""", unsafe_allow_html=True)

# ─── Recipe Data ─────────────────────────────────────────────────────────────
RECIPES = {
    "Breakfast": [
        {
            "name": "Golden Turmeric Chia Pudding",
            "time": "5 min prep + overnight",
            "servings": 2,
            "tags": ["Anti-Inflammatory", "High-Fiber", "Insulin-Stable"],
            "description": "A creamy, fiber-rich pudding that promotes slow glucose release.",
            "ingredients": [
                "1/4 cup chia seeds",
                "1 1/2 cups unsweetened oat milk",
                "1 tsp ground turmeric",
                "1/2 tsp cinnamon",
                "1 tbsp maple syrup",
                "1/4 tsp black pepper",
                "1/2 cup mixed berries (for topping)",
                "1 tbsp hemp seeds (for topping)",
            ],
            "instructions": "Whisk chia seeds, oat milk, turmeric, cinnamon, maple syrup, and pepper in a jar. Refrigerate overnight or at least 4 hours. Stir well before serving. Top with berries and hemp seeds.",
            "why_it_works": "Chia seeds slow glucose absorption via soluble fiber. Turmeric modulates insulin signaling. No spike, sustained energy.",
        },
        {
            "name": "Savory Avocado & Black Bean Toast",
            "time": "10 min",
            "servings": 2,
            "tags": ["High-Protein", "Slow-Carb", "Dopamine-Balanced"],
            "description": "Protein + fat combo blunts morning cortisol-driven hunger.",
            "ingredients": [
                "2 slices whole-grain sourdough bread",
                "1 ripe avocado",
                "1/2 cup canned black beans (rinsed)",
                "1/4 red onion (thinly sliced)",
                "1 tbsp lime juice",
                "1/4 tsp cumin",
                "Salt, red pepper flakes to taste",
                "Fresh cilantro (optional)",
            ],
            "instructions": "Toast bread. Mash avocado with lime juice and salt. Warm black beans with cumin. Spread avocado, top with beans, red onion, cilantro, and pepper flakes.",
            "why_it_works": "Fiber from beans + fat from avocado = glycemic index crusher. Keeps insulin flat for 3–4 hours.",
        },
        {
            "name": "Blueberry Walnut Overnight Oats",
            "time": "5 min prep + overnight",
            "servings": 2,
            "tags": ["Antioxidant-Rich", "Omega-3", "Gut-Supportive"],
            "description": "Resistant starch from cold oats feeds your gut microbiome.",
            "ingredients": [
                "1 cup rolled oats",
                "1 1/4 cups unsweetened almond milk",
                "1/4 cup plain plant-based yogurt",
                "2 tbsp chia seeds",
                "1 tbsp almond butter",
                "1/2 cup fresh blueberries",
                "1/4 cup crushed walnuts",
                "1 tsp vanilla extract",
                "Pinch of salt",
            ],
            "instructions": "Combine oats, almond milk, yogurt, chia, almond butter, vanilla, and salt. Refrigerate overnight. Top with blueberries and walnuts before serving.",
            "why_it_works": "Cold oats have 3x more resistant starch than hot oats — feeds gut bacteria that produce butyrate, reducing inflammation-driven hunger.",
        },
        {
            "name": "Spinach & Mushroom Tofu Scramble",
            "time": "15 min",
            "servings": 2,
            "tags": ["High-Protein", "Iron-Rich", "Hormonal-Regulating"],
            "description": "A protein-dense savory breakfast that supports dopamine synthesis.",
            "ingredients": [
                "14 oz firm tofu (pressed and crumbled)",
                "2 cups fresh spinach",
                "1 cup sliced cremini mushrooms",
                "1/4 cup diced onion",
                "2 garlic cloves (minced)",
                "1 tbsp olive oil",
                "1/2 tsp turmeric",
                "1/4 tsp black pepper",
                "2 tbsp nutritional yeast",
                "1 tbsp soy sauce",
            ],
            "instructions": "Sauté onion and garlic in oil 2 min. Add mushrooms until golden, 4 min. Add tofu with turmeric, pepper, soy sauce. Cook 5 min. Stir in spinach and nutritional yeast until wilted.",
            "why_it_works": "Tyrosine in tofu is a direct dopamine precursor. B12 from nutritional yeast supports neurological reward circuits.",
        },
        {
            "name": "Matcha Green Protein Smoothie",
            "time": "5 min",
            "servings": 1,
            "tags": ["L-Theanine Boost", "Slow-Energy", "Anti-Cravings"],
            "description": "Sustained energy via L-theanine without cortisol-spiking caffeine crash.",
            "ingredients": [
                "1 cup unsweetened coconut milk",
                "1 tbsp matcha powder (ceremonial grade)",
                "1 medium frozen banana",
                "1/2 cup frozen spinach",
                "2 tbsp hemp protein powder",
                "1 tbsp almond butter",
                "1 tsp honey",
                "Ice cubes",
            ],
            "instructions": "Blend all ingredients until completely smooth. Serve immediately.",
            "why_it_works": "L-theanine in matcha modulates dopamine + serotonin without the sharp caffeine crash that triggers cortisol-driven hunger at 11 AM.",
        },
        {
            "name": "Apple Cinnamon Buckwheat Porridge",
            "time": "20 min",
            "servings": 2,
            "tags": ["Gluten-Free", "Insulin-Stabilizing", "High-Fiber"],
            "description": "Buckwheat's D-chiro-inositol directly improves insulin sensitivity.",
            "ingredients": [
                "1 cup buckwheat groats",
                "2 cups water",
                "1 cup unsweetened soy milk",
                "1 medium apple (diced)",
                "1 tsp cinnamon",
                "1/4 tsp nutmeg",
                "1 tbsp flaxseed meal",
                "2 tbsp pecans (chopped)",
                "1 tsp maple syrup",
            ],
            "instructions": "Simmer buckwheat in water 10 min. Add soy milk, apple, cinnamon, nutmeg. Cook 5 more min. Top with flaxseed, pecans, and maple syrup.",
            "why_it_works": "D-chiro-inositol in buckwheat acts as a natural insulin sensitizer. Cinnamon activates GLUT4 receptors, improving glucose uptake.",
        },
        {
            "name": "Banana Almond Butter Protein Muffins",
            "time": "30 min",
            "servings": 6,
            "tags": ["Meal-Prep", "Portable", "Slow-Release"],
            "description": "Batch-cook Sunday, eat metabolically smart all week.",
            "ingredients": [
                "2 ripe bananas (mashed)",
                "1/2 cup almond butter",
                "1/2 cup rolled oats",
                "1/4 cup flaxseed meal",
                "2 tbsp maple syrup",
                "1 tsp vanilla extract",
                "1 tsp baking powder",
                "1/2 tsp cinnamon",
                "1/4 cup dark chocolate chips (optional)",
            ],
            "instructions": "Preheat oven 350°F. Mix all ingredients. Pour into greased muffin tin. Bake 20–22 min until toothpick comes clean. Cool 10 min before removing.",
            "why_it_works": "Ripe banana's fructose is liver-bound and metabolized slowly. Almond butter fat slows gastric emptying and extends satiety.",
        },
        {
            "name": "Papaya Ginger Probiotic Bowl",
            "time": "10 min",
            "servings": 2,
            "tags": ["Gut-Healing", "Enzyme-Rich", "Hormone-Supportive"],
            "description": "Papain enzymes reduce gut inflammation that drives pseudo-hunger.",
            "ingredients": [
                "2 cups fresh papaya (cubed)",
                "1 cup coconut yogurt (plain)",
                "1 tbsp fresh grated ginger",
                "2 tbsp pumpkin seeds",
                "1 tbsp ground flaxseed",
                "1/4 cup granola (low sugar)",
                "Squeeze of lime",
                "Fresh mint leaves",
            ],
            "instructions": "Layer coconut yogurt in bowls. Top with papaya, ginger, pumpkin seeds, flaxseed, and granola. Finish with lime juice and mint.",
            "why_it_works": "Papaya's papain enzyme reduces gut inflammation. Ginger improves gastric motility, reducing false hunger signals from gut dysbiosis.",
        },
    ],

    "Lunch": [
        {
            "name": "Lentil & Roasted Vegetable Power Bowl",
            "time": "35 min",
            "servings": 2,
            "tags": ["High-Protein", "Prebiotic", "Anti-Inflammatory"],
            "description": "A complete amino acid profile with maximum satiety signaling.",
            "ingredients": [
                "1 cup dry green lentils",
                "1 medium sweet potato (cubed)",
                "1 cup broccoli florets",
                "1 red bell pepper (sliced)",
                "2 tbsp olive oil",
                "1 tsp cumin",
                "1 tsp smoked paprika",
                "2 cups mixed greens",
                "2 tbsp tahini",
                "1 tbsp lemon juice",
                "Salt & pepper",
            ],
            "instructions": "Cook lentils per package (20 min). Toss vegetables with oil and spices, roast at 400°F for 25 min. Make tahini dressing with lemon juice + water. Assemble bowls with greens, lentils, vegetables, and dressing.",
            "why_it_works": "Lentils' complete amino profile stimulates CCK and GLP-1 satiety hormones for 4–5 hours. No insulin spike.",
        },
        {
            "name": "Chickpea Avocado Collard Wraps",
            "time": "15 min",
            "servings": 2,
            "tags": ["Raw", "Grain-Free", "Liver-Supporting"],
            "description": "Collard greens provide sulforaphane that supports liver detox pathways.",
            "ingredients": [
                "4 large collard green leaves",
                "1 can (15 oz) chickpeas (rinsed)",
                "1 ripe avocado (mashed)",
                "1/2 cup shredded carrots",
                "1/4 cup diced cucumber",
                "2 tbsp hummus",
                "1 tbsp lemon juice",
                "1/2 tsp garlic powder",
                "Fresh dill",
                "Salt & pepper",
            ],
            "instructions": "Trim collard stems flat. Mix chickpeas with lemon, garlic powder, salt. Spread hummus on leaves, add mashed avocado, chickpeas, carrots, cucumber, and dill. Roll and slice in half.",
            "why_it_works": "Collard leaves' sulforaphane activates NRF2 pathway — the master detox regulator. Chickpeas provide slow-digesting protein that maintains stable glucose.",
        },
        {
            "name": "Black Bean & Quinoa Taco Bowl",
            "time": "25 min",
            "servings": 2,
            "tags": ["Complete-Protein", "Gut-Fed", "Dopamine-Supportive"],
            "description": "Quinoa + black beans form a complete amino acid profile.",
            "ingredients": [
                "1 cup dry quinoa",
                "1 can (15 oz) black beans (rinsed)",
                "1 cup corn kernels (fresh or frozen)",
                "1 cup cherry tomatoes (halved)",
                "1/4 cup red onion (minced)",
                "1 avocado (diced)",
                "2 tbsp lime juice",
                "1 tsp chili powder",
                "1/2 tsp cumin",
                "Fresh cilantro",
                "Salsa for topping",
            ],
            "instructions": "Cook quinoa per package. Warm black beans with cumin and chili. Combine tomatoes, onion, lime, cilantro. Assemble bowls with quinoa, beans, corn, pico, and avocado.",
            "why_it_works": "Quinoa contains phenylalanine — a dopamine precursor. Black bean fiber feeds Akkermansia muciniphila, a gut bacteria linked to reduced inflammation and better insulin sensitivity.",
        },
        {
            "name": "Creamy Tahini Kale & Farro Salad",
            "time": "30 min",
            "servings": 2,
            "tags": ["Bone-Health", "Slow-Carb", "Anti-Fatigue"],
            "description": "Massaged kale + farro delivers sustained energy and reduces hunger hormones.",
            "ingredients": [
                "1 cup dry farro",
                "4 cups chopped kale",
                "1/2 cup cherry tomatoes",
                "1/4 cup dried cranberries",
                "1/4 cup pumpkin seeds",
                "3 tbsp tahini",
                "2 tbsp lemon juice",
                "1 garlic clove (minced)",
                "2 tbsp warm water",
                "1 tbsp olive oil",
                "Salt & pepper",
            ],
            "instructions": "Cook farro 30 min. Massage kale with olive oil and salt 2 min until tender. Whisk tahini, lemon, garlic, water. Toss kale with farro, tomatoes, cranberries, seeds. Drizzle dressing.",
            "why_it_works": "Kale's glucosinolates reduce liver inflammation that disrupts leptin sensitivity. Farro's high protein content (7g/serving) activates mTOR signaling for satiety.",
        },
        {
            "name": "Roasted Tomato Lentil Soup",
            "time": "40 min",
            "servings": 4,
            "tags": ["Lycopene-Rich", "Gut-Motility", "Warm-Satiety"],
            "description": "Warm meals trigger PYY hormones more efficiently than cold meals.",
            "ingredients": [
                "1 cup red lentils",
                "1 can (14 oz) diced tomatoes",
                "4 cups vegetable broth",
                "1 medium onion (diced)",
                "3 garlic cloves (minced)",
                "1 tsp cumin",
                "1 tsp coriander",
                "1/2 tsp turmeric",
                "1/4 tsp cayenne",
                "2 tbsp olive oil",
                "Fresh lemon + parsley",
            ],
            "instructions": "Sauté onion in oil 5 min. Add garlic and spices 1 min. Add tomatoes, broth, lentils. Simmer 25 min until lentils dissolve. Blend partially for texture. Finish with lemon.",
            "why_it_works": "Lycopene from cooked tomatoes reduces TNF-alpha inflammatory markers. Red lentils are 30% protein and dissolve into a thick, highly satiating broth.",
        },
        {
            "name": "Mediterranean Stuffed Bell Peppers",
            "time": "45 min",
            "servings": 4,
            "tags": ["Meal-Prep", "High-Fiber", "Anti-Oxidant"],
            "description": "Preload high-fiber vegetables to trigger stretch receptors and CCK.",
            "ingredients": [
                "4 large bell peppers (tops cut, seeded)",
                "1 cup cooked brown rice",
                "1 can (15 oz) chickpeas (rinsed)",
                "1 cup diced zucchini",
                "1/2 cup sun-dried tomatoes (chopped)",
                "1/4 cup kalamata olives",
                "1 tsp oregano",
                "1 tsp garlic powder",
                "2 tbsp nutritional yeast",
                "2 tbsp tomato paste",
                "Olive oil",
            ],
            "instructions": "Preheat 375°F. Sauté zucchini, chickpeas, tomatoes, olives 5 min. Mix with rice, oregano, garlic, tomato paste, yeast. Fill peppers, drizzle oil, cover foil. Bake 35 min, uncover last 10.",
            "why_it_works": "Bell peppers' capsaicin-adjacent compounds (capsanthin) slightly elevate metabolism. The fiber + protein combination creates a 5-hour satiety window.",
        },
        {
            "name": "Asian Edamame & Brown Rice Noodle Bowl",
            "time": "20 min",
            "servings": 2,
            "tags": ["Phytoestrogen", "Anti-Bloat", "Complete-Protein"],
            "description": "Edamame's isoflavones help regulate estrogen-driven hunger cycles.",
            "ingredients": [
                "6 oz brown rice noodles",
                "1 cup shelled edamame",
                "1 cup shredded purple cabbage",
                "1 cup shredded carrots",
                "3 tbsp tamari",
                "2 tbsp rice vinegar",
                "1 tbsp sesame oil",
                "1 tbsp lime juice",
                "1 tbsp grated ginger",
                "2 garlic cloves (minced)",
                "Sesame seeds, scallions",
            ],
            "instructions": "Cook noodles, run under cold water. Whisk tamari, vinegar, sesame oil, lime, ginger, garlic. Toss noodles, edamame, cabbage, carrots with dressing. Top with seeds and scallions.",
            "why_it_works": "Purple cabbage's anthocyanins improve insulin receptor sensitivity. Edamame provides 18g complete protein per cup — key for PYY satiety hormone release.",
        },
        {
            "name": "White Bean & Greens Stew",
            "time": "30 min",
            "servings": 4,
            "tags": ["High-Fiber", "Prebiotic", "Bone-Density"],
            "description": "Calcium-dense greens + white bean protein prevent the 3 PM energy crash.",
            "ingredients": [
                "2 cans (15 oz each) cannellini beans (rinsed)",
                "4 cups vegetable broth",
                "3 cups chopped Swiss chard",
                "1 can (14 oz) diced tomatoes",
                "1 medium onion (diced)",
                "4 garlic cloves (minced)",
                "1 tsp rosemary",
                "1/2 tsp thyme",
                "2 tbsp olive oil",
                "Red pepper flakes",
                "Lemon zest",
            ],
            "instructions": "Sauté onion and garlic in oil 5 min. Add herbs, tomatoes, broth, and beans. Simmer 15 min. Stir in chard until wilted 3 min. Finish with lemon zest and pepper flakes.",
            "why_it_works": "Cannellini beans top the satiety index charts. Their soluble fiber forms a gel that physically slows glucose absorption in the small intestine.",
        },
    ],

    "Dinner": [
        {
            "name": "Cauliflower & Chickpea Tikka Masala",
            "time": "40 min",
            "servings": 4,
            "tags": ["Anti-Inflammatory", "Spice-Rich", "Gut-Healing"],
            "description": "Spices in tikka masala reduce insulin resistance at the cellular level.",
            "ingredients": [
                "1 large cauliflower (cut into florets)",
                "2 cans (15 oz each) chickpeas (rinsed)",
                "1 can (14 oz) coconut cream",
                "1 can (14 oz) crushed tomatoes",
                "1 large onion (diced)",
                "4 garlic cloves (minced)",
                "1 tbsp grated ginger",
                "2 tbsp tikka masala paste (vegan)",
                "1 tsp turmeric",
                "2 tbsp coconut oil",
                "Fresh cilantro, basmati rice for serving",
            ],
            "instructions": "Sauté onion in coconut oil 5 min. Add garlic, ginger, paste, turmeric 2 min. Add tomatoes, coconut cream. Simmer 10 min. Add cauliflower and chickpeas. Cover and cook 20 min until tender. Serve over basmati.",
            "why_it_works": "Curcumin (turmeric) combined with piperine (from black pepper) achieves 2000% better bioavailability and directly inhibits NF-κB inflammatory pathways.",
        },
        {
            "name": "Smoky Sweet Potato & Black Bean Chili",
            "time": "45 min",
            "servings": 6,
            "tags": ["Meal-Prep", "Slow-Burn", "Microbiome-Fed"],
            "description": "Sweet potato's resistant starch feeds Bifidobacterium — your hunger-regulating gut bacteria.",
            "ingredients": [
                "2 large sweet potatoes (cubed)",
                "2 cans (15 oz each) black beans (rinsed)",
                "1 can (14 oz) diced tomatoes",
                "2 cups vegetable broth",
                "1 large onion (diced)",
                "1 red bell pepper (diced)",
                "3 garlic cloves (minced)",
                "2 tbsp chili powder",
                "1 tsp cumin",
                "1 tsp smoked paprika",
                "Avocado & lime for serving",
            ],
            "instructions": "Sauté onion and pepper 5 min. Add garlic and spices 1 min. Add all remaining ingredients. Simmer covered 30 min until sweet potatoes are tender. Mash slightly for thickness. Serve with avocado.",
            "why_it_works": "Sweet potato is a low-GI food (GI 61 vs white potato's 86) despite its sweetness. Black beans' molybdenum supports sulfur amino acid metabolism.",
        },
        {
            "name": "Walnut & Mushroom Bolognese",
            "time": "50 min",
            "servings": 4,
            "tags": ["Omega-3", "Umami", "Neurotrophic"],
            "description": "Walnuts contain ALA omega-3s that support BDNF — your brain's growth factor.",
            "ingredients": [
                "12 oz whole wheat spaghetti",
                "1 cup raw walnuts (pulsed)",
                "2 cups cremini mushrooms (finely chopped)",
                "1 can (28 oz) crushed tomatoes",
                "1 large onion (diced)",
                "4 garlic cloves (minced)",
                "2 tbsp tomato paste",
                "1/2 cup red wine (or broth)",
                "1 tsp oregano",
                "1 tsp thyme",
                "Nutritional yeast for serving",
            ],
            "instructions": "Pulse walnuts until coarse. Sauté onion 5 min. Add mushrooms until golden 7 min. Add walnuts, garlic, tomato paste 3 min. Deglaze with wine. Add tomatoes and herbs, simmer 20 min. Cook pasta, toss together.",
            "why_it_works": "Mushroom glutamate + walnut umami activates the same satiety receptors as meat, without the insulin-disrupting saturated fat load.",
        },
        {
            "name": "Teriyaki Tempeh & Broccoli Stir-Fry",
            "time": "25 min",
            "servings": 2,
            "tags": ["Fermented", "High-Protein", "Probiotic"],
            "description": "Fermented tempeh contains anti-inflammatory isoflavones and prebiotic fiber.",
            "ingredients": [
                "8 oz tempeh (cubed)",
                "2 cups broccoli florets",
                "1 cup snap peas",
                "1 cup shiitake mushrooms",
                "3 tbsp tamari",
                "2 tbsp maple syrup",
                "1 tbsp rice vinegar",
                "1 tsp sesame oil",
                "2 garlic cloves (minced)",
                "1 tsp grated ginger",
                "Brown rice for serving",
            ],
            "instructions": "Whisk tamari, maple, vinegar, sesame oil, garlic, ginger for sauce. Sauté tempeh until golden 6 min. Remove. Stir-fry broccoli and snap peas 4 min. Add mushrooms 2 min. Return tempeh, pour sauce, toss 2 min. Serve over rice.",
            "why_it_works": "Tempeh's fermentation pre-digests phytic acid, dramatically improving zinc and iron absorption. Shiitake mushrooms contain lentinan — a beta-glucan that modulates immune-driven hunger inflammation.",
        },
        {
            "name": "Spiced Red Lentil Dal with Coconut",
            "time": "35 min",
            "servings": 4,
            "tags": ["Tryptophan-Rich", "Sleep-Supportive", "Anti-Stress"],
            "description": "Red lentils are the richest plant source of tryptophan for serotonin synthesis.",
            "ingredients": [
                "1 1/2 cups red lentils",
                "1 can (14 oz) coconut milk",
                "2 cups vegetable broth",
                "1 can (14 oz) diced tomatoes",
                "1 large onion (diced)",
                "4 garlic cloves (minced)",
                "1 tbsp fresh ginger",
                "2 tbsp ghee or coconut oil",
                "1 tbsp curry powder",
                "1 tsp cumin seeds",
                "Spinach, naan for serving",
            ],
            "instructions": "Toast cumin seeds in oil 30 sec. Add onion, garlic, ginger, curry 5 min. Add tomatoes, lentils, broth, coconut milk. Simmer 20 min until creamy. Stir in spinach. Serve over rice or with naan.",
            "why_it_works": "Tryptophan from red lentils converts to serotonin in the gut (90% of serotonin is made there). Evening meals rich in tryptophan improve sleep quality and reduce next-morning hunger.",
        },
        {
            "name": "Stuffed Portobello Mushrooms with Quinoa",
            "time": "35 min",
            "servings": 4,
            "tags": ["Adaptogenic", "Complete-Protein", "Nerve-Supportive"],
            "description": "Portobello mushrooms contain ergothioneine — a powerful antioxidant for mitochondrial health.",
            "ingredients": [
                "4 large portobello mushrooms (stems removed)",
                "1 cup cooked quinoa",
                "1/2 cup diced onion",
                "1/2 cup diced red pepper",
                "2 garlic cloves (minced)",
                "1/4 cup sun-dried tomatoes",
                "2 tbsp pine nuts",
                "2 tbsp nutritional yeast",
                "1 tsp Italian herbs",
                "Balsamic glaze",
            ],
            "instructions": "Preheat 400°F. Brush mushrooms with oil, bake 10 min. Sauté vegetables and garlic 5 min. Mix with quinoa, tomatoes, pine nuts, yeast, herbs. Fill mushroom caps. Bake 15 min. Drizzle with balsamic.",
            "why_it_works": "Portobello's vitamin D (when UV-exposed) supports the vitamin D receptor that regulates over 1,000 genes, including those governing insulin secretion.",
        },
        {
            "name": "Miso Ginger Noodle Soup",
            "time": "25 min",
            "servings": 2,
            "tags": ["Probiotic", "Gut-Healing", "Anti-Bloat"],
            "description": "Miso's live cultures heal gut permeability that drives inflammatory hunger.",
            "ingredients": [
                "6 cups vegetable broth",
                "3 tbsp white miso paste",
                "6 oz udon or rice noodles",
                "1 cup firm tofu (cubed)",
                "1 cup bok choy (sliced)",
                "1 cup shiitake mushrooms",
                "2 tsp grated ginger",
                "2 garlic cloves (minced)",
                "1 tbsp sesame oil",
                "Scallions, nori strips",
            ],
            "instructions": "Heat broth, do NOT boil. Whisk miso into 1/2 cup warm broth first, then add to pot. Add tofu, bok choy, mushrooms, ginger, garlic. Cook noodles separately. Assemble bowls, top with sesame oil, scallions, nori.",
            "why_it_works": "Never boil miso — heat above 160°F destroys live Lactobacillus cultures. These cultures produce GABA, directly reducing stress-driven hunger signals.",
        },
        {
            "name": "Jackfruit & Pinto Bean Tacos",
            "time": "30 min",
            "servings": 4,
            "tags": ["High-Fiber", "Prebiotic", "Dopamine-Neutral"],
            "description": "Jackfruit's unique texture satisfies the oral-sensory dopamine feedback loop.",
            "ingredients": [
                "2 cans (20 oz) young green jackfruit (drained and shredded)",
                "1 can (15 oz) pinto beans (rinsed)",
                "8 corn tortillas",
                "1 tsp cumin",
                "1 tsp chili powder",
                "1/2 tsp garlic powder",
                "1/2 tsp oregano",
                "1 cup shredded purple cabbage",
                "1 avocado (sliced)",
                "Fresh salsa, lime",
            ],
            "instructions": "Sauté jackfruit in dry pan 5 min to dry out. Add spices and 1/4 cup water, cook 10 min, shredding with fork. Warm pinto beans. Char tortillas. Assemble with cabbage, jackfruit, beans, avocado, salsa.",
            "why_it_works": "Oral textural satisfaction from jackfruit's 'meaty' texture activates somatosensory-dopamine reward circuits without high-sugar ultra-processed foods.",
        },
    ],

    "Snacks": [
        {
            "name": "Cinnamon Roasted Chickpeas",
            "time": "35 min",
            "servings": 4,
            "tags": ["Portable", "Crunch-Dopamine", "Blood-Sugar-Stable"],
            "description": "Replaces ultra-processed crunchy snacks without the dopamine crash.",
            "ingredients": [
                "2 cans (15 oz each) chickpeas (rinsed, dried thoroughly)",
                "1 tbsp olive oil",
                "1 1/2 tsp cinnamon",
                "1/2 tsp cardamom",
                "1 tbsp maple syrup",
                "Pinch of salt",
            ],
            "instructions": "Preheat 425°F. Dry chickpeas completely with paper towels. Toss with oil. Roast 25 min, shaking pan halfway. Toss with cinnamon, cardamom, maple, salt immediately. Cool to crisp.",
            "why_it_works": "The crunch sound itself activates the dorsal striatum (reward circuit) without a glucose spike. Chickpea protein co-activates CCK for satiety — unlike potato chips.",
        },
        {
            "name": "Walnut & Date Energy Balls",
            "time": "15 min",
            "servings": 12,
            "tags": ["No-Bake", "Pre-Workout", "Omega-3"],
            "description": "Nature's perfect pre-workout: natural sugars with omega-3 fat buffer.",
            "ingredients": [
                "1 cup Medjool dates (pitted)",
                "1 cup raw walnuts",
                "2 tbsp cocoa powder",
                "1/2 tsp vanilla extract",
                "1/4 tsp sea salt",
                "1/4 cup shredded coconut (for rolling)",
            ],
            "instructions": "Process walnuts in food processor until crumbly. Add dates, cocoa, vanilla, salt. Process until mixture holds together. Roll into 1-inch balls. Roll in coconut. Refrigerate 30 min to firm up.",
            "why_it_works": "Dates' glucose is paired with walnut fat — this combination activates GIP (Gastric Inhibitory Polypeptide) which signals 'slowing down' to the pancreas, reducing insulin spike.",
        },
        {
            "name": "Guacamole with Jicama Sticks",
            "time": "10 min",
            "servings": 4,
            "tags": ["Prebiotic", "Raw", "Grain-Free"],
            "description": "Jicama's inulin fiber is a superior prebiotic that feeds the gut-brain axis.",
            "ingredients": [
                "2 ripe avocados",
                "1 medium jicama (peeled and cut into sticks)",
                "1 lime (juiced)",
                "1/2 red onion (minced)",
                "1 jalapeño (minced)",
                "Fresh cilantro",
                "1/2 tsp cumin",
                "1/4 tsp garlic powder",
                "Salt to taste",
            ],
            "instructions": "Mash avocados with lime juice, cumin, garlic, salt. Stir in onion, jalapeño, cilantro. Serve with jicama sticks.",
            "why_it_works": "Jicama contains inulin — a prebiotic fiber that specifically feeds Faecalibacterium prausnitzii, the bacteria that produces short-chain fatty acids reducing inflammatory hunger.",
        },
        {
            "name": "Dark Chocolate Almond Chia Bites",
            "time": "20 min + chill",
            "servings": 16,
            "tags": ["Magnesium-Rich", "Stress-Busting", "Anti-Cravings"],
            "description": "Magnesium in dark chocolate reduces cortisol — the #1 driver of stress eating.",
            "ingredients": [
                "1 cup 70%+ dark chocolate chips (dairy-free)",
                "1/4 cup almond butter",
                "2 tbsp chia seeds",
                "2 tbsp hemp seeds",
                "1/4 cup crushed almonds",
                "1 tbsp coconut oil",
                "Pinch sea salt",
            ],
            "instructions": "Melt chocolate with coconut oil in double boiler. Stir in almond butter. Mix in chia, hemp seeds. Pour into mini muffin tin lined with cups. Top with almonds and salt. Refrigerate 2 hours.",
            "why_it_works": "Dark chocolate (70%+) contains 64mg magnesium per 1 oz — magnesium directly downregulates cortisol release from the adrenal glands, cutting stress-driven hunger by up to 40%.",
        },
        {
            "name": "Roasted Seaweed & Edamame Trail Mix",
            "time": "10 min",
            "servings": 4,
            "tags": ["Iodine-Rich", "Thyroid-Supporting", "Mineral-Dense"],
            "description": "Iodine from seaweed supports thyroid hormones that regulate metabolism rate.",
            "ingredients": [
                "1 cup shelled edamame (dry-roasted or frozen and baked)",
                "1 cup roasted seaweed snacks (crumbled)",
                "1/2 cup pumpkin seeds",
                "1/4 cup dried cranberries (unsweetened)",
                "1/4 cup sunflower seeds",
                "1/2 tsp garlic powder",
                "Sprinkle of tamari",
            ],
            "instructions": "Bake frozen edamame at 400°F for 20 min until crispy. Cool. Toss with seaweed, seeds, cranberries. Season with garlic powder and light tamari spray.",
            "why_it_works": "The thyroid produces T3 and T4 hormones that regulate basal metabolic rate. Iodine deficiency slows these hormones — causing false fatigue and hunger signals. Seaweed delivers 100–2000% of daily iodine needs.",
        },
        {
            "name": "Spiced Pumpkin Seed Bark",
            "time": "15 min + chill",
            "servings": 8,
            "tags": ["Zinc-Rich", "Testosterone-Supportive", "Anti-Inflammatory"],
            "description": "Zinc from pumpkin seeds supports leptin receptor sensitivity.",
            "ingredients": [
                "1 cup pumpkin seeds",
                "1 cup 70% dark chocolate (dairy-free, melted)",
                "1 tsp cinnamon",
                "1/4 tsp cayenne",
                "1/4 tsp sea salt",
                "1 tbsp maple syrup",
                "2 tbsp dried goji berries",
            ],
            "instructions": "Line baking sheet with parchment. Mix pumpkin seeds with cinnamon, cayenne, maple. Spread melted chocolate on parchment. Top with seed mixture and goji berries. Sprinkle salt. Chill 1 hour. Break into pieces.",
            "why_it_works": "Zinc from pumpkin seeds (6mg per oz) directly upregulates leptin receptors in the hypothalamus. Leptin is the master 'I'm full' hormone — and most people have zinc-deficient leptin resistance.",
        },
    ],
}

# ─── System Prompt for Hunger Decoder ────────────────────────────────────────
SYSTEM_PROMPT = """You are the Rigged Game Breaker AI — an expert in metabolic health, insulin signaling, dopamine systems, and hormonal hunger regulation. You have read every major study on obesity, metabolic dysfunction, and the food industry's deliberate manipulation of appetite.

Your role: Provide a precise "Biological Diagnosis" when a user describes how they feel, what they're craving, or what's happening in their body.

ALWAYS analyze hunger and symptoms through exactly THREE lenses — label each clearly:

🔴 BIOLOGICAL (Fuel Need): True energy deficit, blood glucose status, cellular energy needs, mitochondrial signals.

🟡 HORMONAL (Insulin/Cortisol/Leptin Dynamics): Insulin spike/crash cycles, leptin resistance, ghrelin timing, cortisol elevation, blood sugar dysregulation.

🟢 DOPAMINERGIC (Reward/Stress Seeking): Dopamine depletion signals, stress-driven reward seeking, food industry conditioning, habitual eating triggers, boredom vs. true hunger.

After your three-lens diagnosis, provide:
1. What is actually happening in the body (1-3 sentences, clinical but clear)
2. The biological root cause (1-2 sentences)
3. An immediate action recommendation — a specific plant-based food, drink, movement, or behavioral intervention

RULES:
- NEVER mention calories. NEVER use the word "calorie" or suggest calorie restriction.
- Do NOT moralize or shame. Be empathetic but scientifically authoritative.
- Use US English.
- Keep responses focused and actionable — no fluff, no filler.
- The game is rigged by food corporations that exploit your dopamine system. Your job is to help users hack back their own biology.
- Tone: Like a brilliant doctor friend who explains exactly what's happening without condescending."""

# ─── Helper: Get Claude Client ────────────────────────────────────────────────
@st.cache_resource
def get_client():
    api_key = (
        st.secrets.get("ANTHROPIC_API_KEY", "")
        or os.environ.get("ANTHROPIC_API_KEY", "")
    )
    return anthropic.Anthropic(api_key=api_key)

# ─── Session State Init ───────────────────────────────────────────────────────
def init_session_state():
    defaults = {
        "email_unlocked": False,
        "user_email": "",
        "chat_history": [],
        "steps": 0,
        "water_glasses": 0,
        "page": "Hunger Decoder",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session_state()

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 1rem 0 0.5rem;">
        <div style="font-size:2rem;">🧬</div>
        <div style="color:#B2AC88; font-weight:700; font-size:1.1rem; letter-spacing:0.5px;">RIGGED GAME BREAKER</div>
        <div style="color:#6B6660; font-size:0.75rem; margin-top:2px;">Metabolic Intelligence Platform</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**Navigation**")

    pages = {
        "🔬 Hunger Decoder": "Hunger Decoder",
        "📊 Metabolic Dashboard": "Metabolic Dashboard",
        "🌿 Recipe Finder": "Recipe Finder",
    }

    for label, page_key in pages.items():
        if st.button(label, key=f"nav_{page_key}", use_container_width=True):
            st.session_state.page = page_key
            st.rerun()

    st.markdown("---")

    # Bundle CTA
    st.markdown("""
    <div class="bundle-card">
        <div style="font-size:0.7rem; color:#9E9A8E; letter-spacing:1px; text-transform:uppercase; margin-bottom:4px;">LIMITED OFFER</div>
        <div style="color:#F0EDE6; font-size:0.95rem; font-weight:600; margin-bottom:8px;">Both Books + Full AI Access</div>
        <div class="bundle-price">$22.50</div>
        <div style="color:#9E9A8E; font-size:0.75rem; text-decoration:line-through; margin-bottom:12px;">$44.00</div>
        <a href="https://www.amazon.com" target="_blank" style="text-decoration:none;">
            <div style="background:#B2AC88; color:#1E1E1E; font-weight:700; border-radius:10px; padding:8px; font-size:0.85rem; cursor:pointer;">
                📦 Get the Bundle →
            </div>
        </a>
        <div style="color:#6B6660; font-size:0.7rem; margin-top:8px;">Amazon KDP · Instant Download</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""
    <div style="color:#4A4640; font-size:0.7rem; text-align:center;">
        Powered by Anthropic Claude<br>
        Built on The Hunger Game Is Rigged Series
    </div>
    """, unsafe_allow_html=True)

# ─── Dev Preview Toggle ───────────────────────────────────────────────────────
st.markdown("""
<div id="_pv_bar" style="
  position:fixed; top:62px; right:14px; z-index:999999;
  display:flex; align-items:center; gap:8px;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <span id="_pv_label" style="
    font-size:0.68rem; color:#888; background:#111;
    padding:2px 8px; border-radius:6px; border:1px solid #333;
    letter-spacing:0.5px;"></span>
  <button id="_pv_btn"
    style="background:#B2AC88;color:#1E1E1E;border:none;border-radius:8px;
           padding:7px 14px;font-size:0.76rem;font-weight:700;cursor:pointer;
           box-shadow:0 2px 10px rgba(0,0,0,0.6);transition:all .15s;
           letter-spacing:0.3px;">
    📱 Mobile
  </button>
</div>
""", unsafe_allow_html=True)

components.html("""
<script>
(function(){
  var p = window.parent;
  var MODES = {
    desktop: { label: '1200px', btn: '📱 Mobile',  bg: '#B2AC88', fg: '#1E1E1E',
               css: 'section[data-testid="stMain"]{max-width:1200px!important;margin:0 auto!important;}' },
    mobile:  { label: '375px',  btn: '🖥️ Desktop', bg: '#4A7A57', fg: '#ffffff',
               css: 'section[data-testid="stMain"]{max-width:375px!important;min-width:375px!important;margin:0 auto!important;border-left:2px solid #555!important;border-right:2px solid #555!important;box-shadow:0 0 50px rgba(0,0,0,.7)!important;}' },
  };

  function styleEl(){
    var el = p.document.getElementById('_pv_style');
    if(!el){ el=p.document.createElement('style'); el.id='_pv_style'; p.document.head.appendChild(el); }
    return el;
  }

  function syncUI(){
    var mode = MODES[p.localStorage.getItem('_pv_mode')||'desktop'];
    var btn  = p.document.getElementById('_pv_btn');
    var lbl  = p.document.getElementById('_pv_label');
    if(!btn) return;
    btn.innerHTML        = mode.btn;
    btn.style.background = mode.bg;
    btn.style.color      = mode.fg;
    if(lbl) lbl.textContent = mode.label;
  }

  function applyMode(){
    styleEl().textContent = MODES[p.localStorage.getItem('_pv_mode')||'desktop'].css;
    syncUI();
  }

  function toggle(){
    var next = (p.localStorage.getItem('_pv_mode')||'desktop')==='desktop' ? 'mobile' : 'desktop';
    p.localStorage.setItem('_pv_mode', next);
    applyMode();
  }

  function wireBtn(){
    var btn = p.document.getElementById('_pv_btn');
    if(btn) btn.onclick = toggle;
  }

  applyMode();
  wireBtn();

  if(!p._pvObserver){
    var t;
    p._pvObserver = new MutationObserver(function(){
      clearTimeout(t); t = setTimeout(function(){ applyMode(); wireBtn(); }, 80);
    });
    p._pvObserver.observe(p.document.body, {childList:true, subtree:true});
  }
})();
</script>
""", height=0)

# ─── Hero Header ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-header">
    <h1>🧬 The Rigged Game Breaker</h1>
    <p>"You've read the science — now let's hack the biology."</p>
</div>
""", unsafe_allow_html=True)

# ─── Email Gate ───────────────────────────────────────────────────────────────
if not st.session_state.email_unlocked:
    st.markdown("""
    <div class="gate-card">
        <div style="font-size:2.5rem; margin-bottom:0.5rem;">🔐</div>
        <h3 style="color:#B2AC88 !important; margin-bottom:0.3rem;">Unlock the Decoder</h3>
        <p style="color:#9E9A8E; font-size:0.9rem; margin-bottom:1.5rem;">
            Enter your email to access the AI-powered Hunger Decoder, Metabolic Dashboard, and 30 plant-based recipes.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        email_input = st.text_input(
            "Email Address",
            placeholder="you@example.com",
            label_visibility="collapsed",
        )
        if st.button("Unlock Free Access →", use_container_width=True):
            if "@" in email_input and "." in email_input:
                st.session_state.user_email = email_input
                st.session_state.email_unlocked = True
                register_lead(email_input)
                st.rerun()
            else:
                st.error("Please enter a valid email address.")

        st.markdown("""
        <div style="text-align:center; color:#4A4640; font-size:0.72rem; margin-top:0.8rem;">
            🔒 No spam. We respect your inbox.<br>
            Used only to send you updates on the book series.
        </div>
        """, unsafe_allow_html=True)
    st.stop()

# ─── Navigation (hidden radio = state trigger, visible navbar injected via JS) ──
_nav_opts = ["🔬 Decoder", "📊 Dashboard", "🌿 Recipes"]
_nav_map  = {
    "🔬 Decoder":   "Hunger Decoder",
    "📊 Dashboard": "Metabolic Dashboard",
    "🌿 Recipes":   "Recipe Finder",
}
_nav_rev = {v: k for k, v in _nav_map.items()}
_nav_sel = st.radio(
    "nav",
    _nav_opts,
    index=_nav_opts.index(_nav_rev.get(st.session_state.page, "🔬 Decoder")),
    horizontal=True,
    label_visibility="collapsed",
    key="main_nav_radio",
)
if _nav_map[_nav_sel] != st.session_state.page:
    st.session_state.page = _nav_map[_nav_sel]
    st.rerun()

components.html("""
<script>
(function(){
  var p = window.parent;

  var DESKTOP_LABELS = ['🔬 Hunger Decoder', '📊 Metabolic Dashboard', '🌿 Recipe Finder'];
  var MOBILE_LABELS  = ['🔬 Decoder',        '📊 Dashboard',           '🌿 Recipes'];

  function isMobile(){ return p.innerWidth <= 768; }

  function getCurrentIdx(){
    var inputs = p.document.querySelectorAll('div[data-testid="stRadio"] input[type="radio"]');
    for(var i = 0; i < inputs.length; i++){
      if(inputs[i].checked) return i;
    }
    return 0;
  }

  function clickNav(idx){
    var items = p.document.querySelectorAll('div[data-testid="stRadio"] [data-baseweb="radio"]');
    if(items[idx]) items[idx].click();
  }

  function styleBtn(btn, active, mob){
    if(mob){
      btn.style.cssText =
        'flex:1;padding:8px 4px;border:none;border-radius:10px;'+
        'font-size:0.82rem;font-weight:'+(active?'700':'500')+';'+
        'cursor:pointer;font-family:Inter,sans-serif;transition:all 0.15s;'+
        'background:'+(active?'rgba(178,172,136,0.18)':'transparent')+';'+
        'color:'+(active?'#B2AC88':'#9E9A8E')+';border-bottom:'+(active?'2px solid #B2AC88':'2px solid transparent')+';'+
        'border-radius:0;';
    } else {
      btn.style.cssText =
        'padding:10px 28px;border-radius:10px;border:none;'+
        'font-size:0.95rem;font-weight:'+(active?'700':'600')+';'+
        'cursor:pointer;font-family:Inter,sans-serif;transition:all 0.15s;'+
        'background:'+(active?'#1E1E1E':'rgba(0,0,0,0.12)')+';'+
        'color:'+(active?'#B2AC88':'#2A2A2A')+';letter-spacing:0.2px;'+
        'box-shadow:'+(active?'inset 0 0 0 2px #B2AC88':'none')+';';
    }
  }

  function buildNav(){
    var mob = isMobile();
    var labels = mob ? MOBILE_LABELS : DESKTOP_LABELS;
    var current = getCurrentIdx();

    var existing = p.document.getElementById('_cnav');
    if(existing){
      /* just refresh active states */
      var btns = existing.querySelectorAll('button');
      btns.forEach(function(btn, i){ styleBtn(btn, i===current, mob); });
      return;
    }

    var nav = p.document.createElement('div');
    nav.id = '_cnav';
    if(mob){
      nav.style.cssText =
        'position:fixed;bottom:0;left:0;right:0;width:100vw;height:64px;z-index:99999;'+
        'background:#1A1A1A;border-top:2px solid #B2AC88;'+
        'display:flex;align-items:stretch;justify-content:space-around;'+
        'box-shadow:0 -4px 20px rgba(0,0,0,0.6);font-family:Inter,sans-serif;';
    } else {
      nav.style.cssText =
        'position:fixed;top:0;left:0;right:0;width:100vw;height:60px;z-index:99999;'+
        'background:#B2AC88;'+
        'display:flex;align-items:center;justify-content:center;gap:8px;'+
        'box-shadow:0 4px 20px rgba(0,0,0,0.5);font-family:Inter,sans-serif;';
    }

    labels.forEach(function(label, idx){
      var btn = p.document.createElement('button');
      btn.textContent = label;
      styleBtn(btn, idx===current, mob);
      btn.addEventListener('mouseenter', function(){
        if(idx !== getCurrentIdx()){
          this.style.background = mob ? 'rgba(178,172,136,0.08)' : 'rgba(0,0,0,0.22)';
        }
      });
      btn.addEventListener('mouseleave', function(){
        styleBtn(this, idx===getCurrentIdx(), mob);
      });
      btn.addEventListener('click', function(){ clickNav(idx); });
      nav.appendChild(btn);
    });

    p.document.body.appendChild(nav);
  }

  buildNav();

  if(!p._cnavObs){
    var t;
    p._cnavObs = new MutationObserver(function(){
      clearTimeout(t); t = setTimeout(buildNav, 120);
    });
    p._cnavObs.observe(p.document.body, {childList:true, subtree:true});
  }
})();
</script>
""", height=0)

# ─── Page: Hunger Decoder ─────────────────────────────────────────────────────
if st.session_state.page == "Hunger Decoder":
    st.markdown('<div class="section-title">🔬 The Hunger Decoder</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="info-box">
        Describe exactly how you feel right now — your energy, mood, what you're craving, when you last ate, your stress level.
        The AI will decode the biological root cause and tell you what your body <em>actually</em> needs.
    </div>
    """, unsafe_allow_html=True)

    # Display chat history
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(f"""
            <div class="chat-user">
                <div class="chat-label">You</div>
                {msg["content"]}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="chat-ai">
                <div class="chat-label">Rigged Game Breaker AI</div>
                {md_to_html(msg["content"])}
            </div>
            """, unsafe_allow_html=True)

    # Input
    st.markdown("<br>", unsafe_allow_html=True)
    user_input = st.text_area(
        "Describe how you feel right now...",
        placeholder="Example: 'It's 3 PM, I had a big lunch 2 hours ago but I'm already craving something sweet. I feel a bit anxious and tired, brain foggy. I didn't sleep great last night...'",
        height=120,
        key="hunger_input",
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        send_clicked = st.button("🔬 Run Biological Diagnosis", use_container_width=True)
    with col2:
        st.button(
            "🗑️ Clear Chat",
            use_container_width=True,
            on_click=lambda: st.session_state.update({"chat_history": []}),
        )

    if send_clicked and user_input.strip():
        # Add user message
        st.session_state.chat_history.append({"role": "user", "content": user_input.strip()})

        # Build messages for API
        messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in st.session_state.chat_history
        ]

        # Stream response
        with st.spinner("Analyzing your biological signals..."):
            try:
                client = get_client()
                full_response = ""
                response_placeholder = st.empty()

                with client.messages.stream(
                    model="claude-sonnet-4-6",
                    max_tokens=1024,
                    system=SYSTEM_PROMPT,
                    messages=messages,
                ) as stream:
                    for text in stream.text_stream:
                        full_response += text
                        response_placeholder.markdown(f"""
                        <div class="chat-ai">
                            <div class="chat-label">Rigged Game Breaker AI</div>
                            {md_to_html(full_response)}▌
                        </div>
                        """, unsafe_allow_html=True)

                response_placeholder.empty()
                st.session_state.chat_history.append(
                    {"role": "assistant", "content": full_response}
                )
                st.rerun()

            except anthropic.AuthenticationError:
                st.error("⚠️ API key not configured. Set the ANTHROPIC_API_KEY environment variable.")
            except Exception as e:
                st.error(f"Connection error: {str(e)}")

    elif send_clicked:
        st.warning("Please describe how you're feeling before running the diagnosis.")

    # Suggested prompts
    st.markdown("---")
    st.markdown("**Try one of these:**")
    examples = [
        "It's 10 AM, I just had breakfast an hour ago but I'm already thinking about food. I feel restless.",
        "I'm craving chocolate and salty chips simultaneously. Work stress is high today.",
        "I haven't eaten since 7 AM, it's now 1 PM, I feel shaky and irritable and can't focus.",
        "I just finished a workout and feel ravenous even though I ate beforehand.",
    ]
    cols = st.columns(2)
    for i, example in enumerate(examples):
        with cols[i % 2]:
            if st.button(f"💬 {example[:60]}...", key=f"ex_{i}", use_container_width=True):
                st.session_state.chat_history.append({"role": "user", "content": example})
                with st.spinner("Analyzing..."):
                    try:
                        client = get_client()
                        full_response = ""
                        messages = [{"role": msg["role"], "content": msg["content"]}
                                    for msg in st.session_state.chat_history]
                        with client.messages.stream(
                            model="claude-sonnet-4-6",
                            max_tokens=1024,
                            system=SYSTEM_PROMPT,
                            messages=messages,
                        ) as stream:
                            for text in stream.text_stream:
                                full_response += text
                        st.session_state.chat_history.append(
                            {"role": "assistant", "content": full_response}
                        )
                        st.rerun()
                    except anthropic.AuthenticationError:
                        st.error("⚠️ Set ANTHROPIC_API_KEY to enable AI responses.")
                    except Exception as e:
                        st.error(str(e))

# ─── Page: Metabolic Dashboard ────────────────────────────────────────────────
elif st.session_state.page == "Metabolic Dashboard":
    st.markdown('<div class="section-title">📊 Metabolic Dashboard</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="info-box">
        Track the two highest-leverage daily habits for metabolic health: movement and hydration.
        Both directly modulate insulin sensitivity, cortisol, and hunger hormones.
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    # ── Step Tracker ──
    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 👟 Daily Step Tracker")

        TARGET_STEPS = 10_000
        steps = st.number_input(
            "Steps taken today",
            min_value=0,
            max_value=50000,
            value=st.session_state.steps,
            step=500,
            key="steps_input",
        )
        st.session_state.steps = steps

        step_pct = min(steps / TARGET_STEPS, 1.0)
        step_pct_display = int(step_pct * 100)
        remaining = max(TARGET_STEPS - steps, 0)

        st.progress(step_pct)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{steps:,}</div>
                <div class="metric-label">Steps Done</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{step_pct_display}%</div>
                <div class="metric-label">Goal Progress</div>
            </div>""", unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{remaining:,}</div>
                <div class="metric-label">To Goal</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        if steps >= TARGET_STEPS:
            st.success("🎯 Daily step goal achieved! GLUT4 transporters are activated — your muscles are absorbing glucose without insulin.")
        elif steps >= 7500:
            st.info("💪 Great progress! Post-meal walks of 10 min reduce glucose spikes by up to 30%.")
        elif steps >= 5000:
            st.warning("⚡ Keep moving — your insulin sensitivity improves with each additional 1,000 steps.")
        else:
            st.error("🔴 Low movement increases insulin resistance. Even a 15-minute walk after meals dramatically improves glucose response.")

        st.markdown("**The Science:**")
        st.markdown("""
        <div class="info-box">
            Walking activates GLUT4 transporters in muscle cells — glucose enters cells WITHOUT insulin.
            This directly reduces the insulin demand that drives fat storage and hunger cycles.
            10,000 steps improves insulin sensitivity by 30–40% over sedentary behavior.
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Hydration Tracker ──
    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 💧 Hydration Tracker")

        TARGET_GLASSES = 8
        glasses = st.number_input(
            "Glasses of water today (8 oz each)",
            min_value=0,
            max_value=20,
            value=st.session_state.water_glasses,
            step=1,
            key="water_input",
        )
        st.session_state.water_glasses = glasses

        water_pct = min(glasses / TARGET_GLASSES, 1.0)
        water_pct_display = int(water_pct * 100)
        oz_done = glasses * 8
        oz_target = TARGET_GLASSES * 8

        st.progress(water_pct)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{glasses}</div>
                <div class="metric-label">Glasses</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{oz_done} oz</div>
                <div class="metric-label">Total Fluid</div>
            </div>""", unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{water_pct_display}%</div>
                <div class="metric-label">of Daily Goal</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        if glasses >= TARGET_GLASSES:
            st.success("💧 Optimal hydration achieved! Your hypothalamus is not confusing thirst signals for hunger.")
        elif glasses >= 6:
            st.info("👍 Good hydration. Keep going — the last 2 glasses matter for kidney and cortisol regulation.")
        elif glasses >= 4:
            st.warning("⚠️ Mild dehydration can mimic hunger. Drink 2 more glasses before your next meal.")
        else:
            st.error("🔴 Dehydration suppresses leptin and raises cortisol — you may be mistaking thirst for food cravings right now.")

        st.markdown("**The Science:**")
        st.markdown("""
        <div class="info-box">
            Dehydration of just 1–2% body weight increases cortisol levels and suppresses leptin (the 'full' hormone).
            The hypothalamus uses the same thirst/hunger neural pathways — mild dehydration is frequently misread as hunger.
            Drinking 16 oz of water before a meal reduces caloric intake by 22%.
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Weekly Metabolic Insight ──
    st.markdown("---")
    st.markdown('<div class="section-title">📈 Metabolic Insight Engine</div>', unsafe_allow_html=True)

    total_score = (min(steps / TARGET_STEPS, 1.0) * 50) + (min(glasses / TARGET_GLASSES, 1.0) * 50)
    score_int = int(total_score)

    score_col, insight_col = st.columns([1, 2])
    with score_col:
        st.markdown(f"""
        <div class="metric-card" style="padding: 2rem;">
            <div style="font-size:3rem; font-weight:700; color:#B2AC88;">{score_int}</div>
            <div style="color:#9E9A8E; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.5px;">Metabolic Score</div>
            <div style="color:#6B6660; font-size:0.7rem; margin-top:8px;">out of 100</div>
        </div>
        """, unsafe_allow_html=True)

    with insight_col:
        if score_int >= 80:
            insight = "Your fundamentals are locked in. Today's movement and hydration are working together to keep insulin sensitivity high and cortisol regulated. The dopamine system stays stable when the biological foundation is solid."
            color = "#6B9E78"
        elif score_int >= 50:
            insight = "You're partially metabolically optimized today. Incomplete hydration or movement leaves gaps that cortisol will fill — often showing up as afternoon energy crashes and sweet cravings."
            color = "#B2AC88"
        else:
            insight = "Your metabolic foundation is under-supported today. Low movement + low hydration creates a stress hormonal state that the food industry is specifically designed to exploit. Start with a 10-minute walk and 2 glasses of water."
            color = "#9E4A4A"

        st.markdown(f"""
        <div class="card" style="border-left: 3px solid {color};">
            <div style="font-size:0.9rem; line-height:1.6; color:#F0EDE6;">{insight}</div>
        </div>
        """, unsafe_allow_html=True)

# ─── Page: Recipe Finder ──────────────────────────────────────────────────────
elif st.session_state.page == "Recipe Finder":
    st.markdown('<div class="section-title">🌿 Plant-Based Recipe Finder</div>', unsafe_allow_html=True)

    # Serialize recipe data for embedding in JS — json.dumps handles all escaping
    recipes_json = json.dumps(RECIPES)

    recipe_html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, sans-serif;
    background: #1E1E1E;
    color: #F0EDE6;
    padding: 0 4px 24px;
  }}

  /* ── Info banner ── */
  .info-box {{
    background: rgba(178,172,136,0.07);
    border-left: 3px solid #8C8770;
    border-radius: 10px;
    padding: 10px 14px;
    color: #9E9A8E;
    font-size: 0.88rem;
    line-height: 1.5;
    margin-bottom: 18px;
  }}

  /* ── Stats row ── */
  .stats-row {{
    display: flex;
    gap: 10px;
    margin-bottom: 18px;
    flex-wrap: wrap;
  }}
  .stat-card {{
    flex: 1;
    min-width: 80px;
    background: #252525;
    border: 1px solid #333;
    border-radius: 12px;
    padding: 12px 8px;
    text-align: center;
  }}
  .stat-emoji {{ font-size: 1.2rem; }}
  .stat-value {{ font-size: 1.5rem; font-weight: 700; color: #B2AC88; }}
  .stat-label {{ font-size: 0.68rem; color: #6B6660; text-transform: uppercase; letter-spacing: 0.4px; }}

  /* ── Controls ── */
  .controls {{ margin-bottom: 18px; }}

  .filter-row {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 10px;
  }}
  .filter-btn {{
    background: #252525;
    color: #9E9A8E;
    border: 1px solid #333;
    border-radius: 20px;
    padding: 6px 16px;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
    outline: none;
  }}
  .filter-btn:hover {{ border-color: #8C8770; color: #F0EDE6; }}
  .filter-btn.active {{
    background: #B2AC88;
    color: #1E1E1E;
    border-color: #B2AC88;
  }}

  #search {{
    width: 100%;
    background: #252525;
    border: 1px solid #333;
    border-radius: 10px;
    padding: 9px 14px;
    color: #F0EDE6;
    font-size: 0.9rem;
    outline: none;
    transition: border-color 0.15s;
  }}
  #search:focus {{ border-color: #B2AC88; box-shadow: 0 0 0 2px rgba(178,172,136,0.15); }}
  #search::placeholder {{ color: #4A4640; }}

  /* ── Category heading ── */
  .cat-header {{
    font-size: 1.1rem;
    font-weight: 700;
    color: #B2AC88;
    border-bottom: 2px solid #8C8770;
    padding-bottom: 6px;
    margin: 22px 0 10px;
  }}

  /* ── Recipe card ── */
  .recipe-card {{
    background: #252525;
    border: 1px solid #333;
    border-radius: 14px;
    margin-bottom: 8px;
    overflow: hidden;
    transition: border-color 0.15s;
  }}
  .recipe-card:hover {{ border-color: #5A5650; }}
  .recipe-card.open {{ border-color: #8C8770; }}

  .recipe-card-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 16px;
    cursor: pointer;
    user-select: none;
    gap: 12px;
  }}
  .recipe-card-header:hover {{ background: rgba(255,255,255,0.02); }}

  .header-left {{ flex: 1; min-width: 0; }}
  .recipe-name {{
    font-size: 0.95rem;
    font-weight: 600;
    color: #F0EDE6;
    margin-bottom: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .recipe-desc {{
    font-size: 0.78rem;
    color: #6B6660;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}

  .header-meta {{
    display: flex;
    align-items: center;
    gap: 10px;
    flex-shrink: 0;
  }}
  .meta-pill {{
    font-size: 0.72rem;
    color: #8C8770;
    white-space: nowrap;
  }}
  .chevron {{
    font-size: 0.75rem;
    color: #6B6660;
    transition: transform 0.2s ease;
    flex-shrink: 0;
  }}
  .recipe-card.open .chevron {{ transform: rotate(180deg); }}

  /* ── Card body ── */
  .recipe-card-body {{
    display: none;
    padding: 0 16px 16px;
    border-top: 1px solid #2C2C2C;
  }}
  .recipe-card.open .recipe-card-body {{ display: block; }}

  .body-grid {{
    display: grid;
    grid-template-columns: 2fr 3fr;
    gap: 14px;
    margin-top: 14px;
  }}
  @media (max-width: 600px) {{
    .body-grid {{ grid-template-columns: 1fr; }}
  }}

  .tags-row {{ margin-bottom: 10px; }}
  .tag-badge {{
    display: inline-block;
    background: rgba(178,172,136,0.12);
    color: #B2AC88;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.7rem;
    font-weight: 600;
    margin: 2px 2px 2px 0;
  }}

  .meta-row {{
    font-size: 0.82rem;
    color: #9E9A8E;
    margin-bottom: 4px;
  }}
  .meta-row strong {{ color: #F0EDE6; }}

  .why-box {{
    background: rgba(178,172,136,0.07);
    border-left: 3px solid #8C8770;
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 0.82rem;
    color: #9E9A8E;
    line-height: 1.5;
    margin-top: 10px;
  }}
  .section-label {{
    font-size: 0.75rem;
    font-weight: 700;
    color: #B2AC88;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 6px;
    margin-top: 12px;
  }}
  .section-label:first-child {{ margin-top: 0; }}

  .ingredients-list {{
    list-style: disc;
    padding-left: 16px;
  }}
  .ingredients-list li {{
    font-size: 0.85rem;
    color: #D0CCC0;
    margin-bottom: 3px;
    line-height: 1.4;
  }}

  .instructions-box {{
    background: #2A2A2A;
    border: 1px solid #333;
    border-radius: 10px;
    padding: 10px 12px;
    font-size: 0.85rem;
    color: #C0BCB6;
    line-height: 1.6;
    margin-top: 0;
  }}

  /* ── Empty state ── */
  .empty-state {{
    text-align: center;
    padding: 40px 20px;
    color: #4A4640;
    font-size: 0.9rem;
  }}

  /* ── Mobile ── */
  @media (max-width: 500px) {{
    body {{ padding: 0 2px 20px; }}
    .stats-row {{ gap: 6px; }}
    .stat-card {{ min-width: 60px; padding: 8px 4px; }}
    .stat-value {{ font-size: 1.2rem; }}
    .stat-label {{ font-size: 0.6rem; }}
    .filter-btn {{ padding: 5px 10px; font-size: 0.76rem; }}
    .recipe-card-header {{ padding: 10px 12px; }}
    .recipe-name {{ font-size: 0.88rem; }}
    .meta-pill {{ font-size: 0.66rem; }}
    .recipe-card-body {{ padding: 0 12px 12px; }}
    .bundle-cta {{ padding: 14px; }}
    .bundle-price {{ font-size: 1.4rem; }}
    .cat-header {{ font-size: 0.95rem; }}
  }}

  /* ── Bundle CTA ── */
  .bundle-cta {{
    background: linear-gradient(135deg, #252520, #1E1E18);
    border: 1px solid #8C8770;
    border-radius: 14px;
    padding: 20px;
    text-align: center;
    margin-top: 24px;
  }}
  .bundle-cta-eyebrow {{ font-size: 0.68rem; color: #9E9A8E; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 6px; }}
  .bundle-cta-title {{ font-size: 1rem; font-weight: 700; color: #F0EDE6; margin-bottom: 4px; }}
  .bundle-cta-sub {{ font-size: 0.82rem; color: #9E9A8E; margin-bottom: 10px; }}
  .bundle-price {{ font-size: 1.8rem; font-weight: 700; color: #B2AC88; }}
  .bundle-old {{ font-size: 0.78rem; color: #6B6660; text-decoration: line-through; margin-bottom: 12px; }}
  .bundle-btn {{
    display: inline-block;
    background: #B2AC88;
    color: #1E1E1E;
    font-weight: 700;
    border-radius: 10px;
    padding: 10px 22px;
    font-size: 0.88rem;
    text-decoration: none;
    cursor: pointer;
  }}
</style>
</head>
<body>

<div class="info-box">
  30 metabolically-intelligent recipes engineered around the three hunger lenses —
  biological fuel, hormonal balance, and dopaminergic satisfaction.
  Every recipe keeps insulin flat, gut bacteria fed, and dopamine loops healthy.
</div>

<!-- Stats -->
<div class="stats-row" id="stats-row"></div>

<!-- Controls -->
<div class="controls">
  <div class="filter-row" id="filter-row"></div>
  <input id="search" type="text" placeholder="Search by ingredient, tag, or name…">
</div>

<!-- Recipe list -->
<div id="recipe-list"></div>

<!-- Bundle CTA -->
<div class="bundle-cta">
  <div class="bundle-cta-eyebrow">Want the full recipe system?</div>
  <div class="bundle-cta-title">The Complete Rigged Game Breaker Protocol</div>
  <div class="bundle-cta-sub">200+ recipes · Meal planning · 12-week metabolic reset · Full AI coaching</div>
  <div class="bundle-price">$22.50</div>
  <div class="bundle-old">$44.00</div>
  <a class="bundle-btn" href="https://www.amazon.com" target="_blank">📦 Get the Bundle on Amazon →</a>
</div>

<script>
(function () {{
  const RECIPES = {recipes_json};
  const CAT_META = {{
    All:       {{ emoji: '🌿', label: 'All' }},
    Breakfast: {{ emoji: '🌅', label: 'Breakfast' }},
    Lunch:     {{ emoji: '☀️',  label: 'Lunch' }},
    Dinner:    {{ emoji: '🌙', label: 'Dinner' }},
    Snacks:    {{ emoji: '🍎', label: 'Snacks' }},
  }};
  const CATS = ['Breakfast', 'Lunch', 'Dinner', 'Snacks'];

  let activeCategory = 'All';
  let searchTerm = '';

  /* ── Stats row ── */
  function buildStats() {{
    const row = document.getElementById('stats-row');
    const total = CATS.reduce((n, c) => n + RECIPES[c].length, 0);
    const items = [['🌿', 'Total', total], ...CATS.map(c => [CAT_META[c].emoji, c, RECIPES[c].length])];
    items.forEach(([emoji, label, count]) => {{
      const card = document.createElement('div');
      card.className = 'stat-card';
      card.innerHTML =
        '<div class="stat-emoji">' + emoji + '</div>' +
        '<div class="stat-value">' + count + '</div>' +
        '<div class="stat-label">' + label + '</div>';
      row.appendChild(card);
    }});
  }}

  /* ── Filter buttons ── */
  function buildFilterButtons() {{
    const row = document.getElementById('filter-row');
    ['All', ...CATS].forEach(cat => {{
      const btn = document.createElement('button');
      btn.className = 'filter-btn' + (cat === 'All' ? ' active' : '');
      btn.dataset.cat = cat;
      btn.textContent = (cat === 'All' ? '🌿 ' : CAT_META[cat].emoji + ' ') + cat;
      btn.addEventListener('click', () => {{
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeCategory = cat;
        buildRecipes();
      }});
      row.appendChild(btn);
    }});
  }}

  /* ── Search listener ── */
  function initSearch() {{
    document.getElementById('search').addEventListener('input', function (e) {{
      searchTerm = e.target.value ? e.target.value.toLowerCase().trim() : '';
      buildRecipes();
    }});
  }}

  /* ── Build recipe cards ── */
  function buildRecipes() {{
    const container = document.getElementById('recipe-list');
    container.innerHTML = '';

    const catsToShow = activeCategory === 'All' ? CATS : [activeCategory];
    let totalShown = 0;

    catsToShow.forEach(cat => {{
      let recipes = RECIPES[cat];

      // Search filter — guard against null/undefined searchTerm
      if (searchTerm) {{
        recipes = recipes.filter(r =>
          r.name.toLowerCase().includes(searchTerm) ||
          r.description.toLowerCase().includes(searchTerm) ||
          r.tags.some(t => t.toLowerCase().includes(searchTerm)) ||
          r.ingredients.some(ing => ing.toLowerCase().includes(searchTerm))
        );
      }}

      if (!recipes.length) return;
      totalShown += recipes.length;

      // Category heading
      const heading = document.createElement('div');
      heading.className = 'cat-header';
      heading.textContent = CAT_META[cat].emoji + ' ' + cat + ' (' + recipes.length + ' recipes)';
      container.appendChild(heading);

      recipes.forEach(recipe => {{
        const card = document.createElement('div');
        card.className = 'recipe-card';

        /* ── Header (click to toggle) ── */
        const header = document.createElement('div');
        header.className = 'recipe-card-header';
        header.addEventListener('click', () => card.classList.toggle('open'));

        const left = document.createElement('div');
        left.className = 'header-left';

        const nameEl = document.createElement('div');
        nameEl.className = 'recipe-name';
        nameEl.textContent = recipe.name;

        const descEl = document.createElement('div');
        descEl.className = 'recipe-desc';
        descEl.textContent = recipe.description;

        left.appendChild(nameEl);
        left.appendChild(descEl);

        const meta = document.createElement('div');
        meta.className = 'header-meta';

        const timePill = document.createElement('span');
        timePill.className = 'meta-pill';
        timePill.textContent = '⏱ ' + recipe.time;

        const srvPill = document.createElement('span');
        srvPill.className = 'meta-pill';
        srvPill.textContent = '👥 ' + recipe.servings;

        const chevron = document.createElement('span');
        chevron.className = 'chevron';
        chevron.textContent = '▼';

        meta.appendChild(timePill);
        meta.appendChild(srvPill);
        meta.appendChild(chevron);

        header.appendChild(left);
        header.appendChild(meta);
        card.appendChild(header);

        /* ── Body (hidden until open) ── */
        const body = document.createElement('div');
        body.className = 'recipe-card-body';

        const grid = document.createElement('div');
        grid.className = 'body-grid';

        // Left column: tags + meta + why-it-works
        const leftCol = document.createElement('div');

        const tagsRow = document.createElement('div');
        tagsRow.className = 'tags-row';
        recipe.tags.forEach(tag => {{
          const badge = document.createElement('span');
          badge.className = 'tag-badge';
          badge.textContent = tag;
          tagsRow.appendChild(badge);
        }});
        leftCol.appendChild(tagsRow);

        const timeMeta = document.createElement('div');
        timeMeta.className = 'meta-row';
        timeMeta.innerHTML = '⏱️ <strong>' + recipe.time + '</strong>';
        leftCol.appendChild(timeMeta);

        const srvMeta = document.createElement('div');
        srvMeta.className = 'meta-row';
        srvMeta.innerHTML = '👥 <strong>' + recipe.servings + ' servings</strong>';
        leftCol.appendChild(srvMeta);

        const whyLabel = document.createElement('div');
        whyLabel.className = 'section-label';
        whyLabel.textContent = '🔬 Why It Works';
        leftCol.appendChild(whyLabel);

        const whyBox = document.createElement('div');
        whyBox.className = 'why-box';
        whyBox.textContent = recipe.why_it_works;
        leftCol.appendChild(whyBox);

        // Right column: ingredients + instructions
        const rightCol = document.createElement('div');

        const ingLabel = document.createElement('div');
        ingLabel.className = 'section-label';
        ingLabel.textContent = '📋 Ingredients';
        rightCol.appendChild(ingLabel);

        const ul = document.createElement('ul');
        ul.className = 'ingredients-list';
        recipe.ingredients.forEach(ing => {{
          const li = document.createElement('li');
          li.textContent = ing;
          ul.appendChild(li);
        }});
        rightCol.appendChild(ul);

        const instrLabel = document.createElement('div');
        instrLabel.className = 'section-label';
        instrLabel.textContent = '👨‍🍳 Instructions';
        rightCol.appendChild(instrLabel);

        const instrBox = document.createElement('div');
        instrBox.className = 'instructions-box';
        instrBox.textContent = recipe.instructions;
        rightCol.appendChild(instrBox);

        grid.appendChild(leftCol);
        grid.appendChild(rightCol);
        body.appendChild(grid);
        card.appendChild(body);
        container.appendChild(card);
      }});
    }});

    // Empty state
    if (totalShown === 0) {{
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.textContent = searchTerm
        ? 'No recipes found for "' + searchTerm + '". Try a different keyword.'
        : 'No recipes in this category.';
      container.appendChild(empty);
    }}
  }}

  /* ── Init on DOM ready ── */
  document.addEventListener('DOMContentLoaded', function () {{
    buildStats();
    buildFilterButtons();
    initSearch();
    buildRecipes();
  }});
}})();
</script>
</body>
</html>
"""

    components.html(recipe_html, height=3200, scrolling=True)
