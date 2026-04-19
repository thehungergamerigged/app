# 🧬 Rigged Game Breaker

> *"You've read the science — now let's hack the biology."*

A companion web app for the **The Hunger Game Is Rigged** book series. Powered by Claude AI, it helps readers decode their hunger through metabolic science and find plant-based recipes engineered for hormonal balance.

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app.streamlit.app)

---

## Features

- **🔬 Hunger Decoder** — AI chat that diagnoses hunger through three biological lenses: Biological (fuel need), Hormonal (insulin/cortisol dynamics), and Dopaminergic (reward/stress seeking). Powered by Claude.
- **📊 Metabolic Dashboard** — Step tracker (10,000-step goal) and hydration tracker with science-backed context.
- **🌿 Recipe Finder** — 30 plant-based recipes across Breakfast, Lunch, Dinner, and Snacks with real-time search and filtering.

---

## Deploy to Streamlit Cloud

### 1. Push to GitHub

```bash
git init
git add app.py requirements.txt .streamlit/config.toml README.md
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### 2. Connect to Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
2. Click **New app**
3. Select your repository and set **Main file path** to `app.py`
4. Click **Deploy**

### 3. Add your API key

In the Streamlit Cloud dashboard, go to **Settings → Secrets** and add:

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

---

## Run Locally

```bash
pip install -r requirements.txt
```

Set your API key in one of two ways:

**Option A — `.streamlit/secrets.toml`** (recommended for local dev):
```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

**Option B — environment variable**:
```bash
# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# macOS / Linux
export ANTHROPIC_API_KEY="sk-ant-..."
```

Then run:
```bash
streamlit run app.py
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| UI | Streamlit 1.40+ |
| AI | Anthropic Claude (claude-sonnet-4-6) |
| Styling | Custom CSS — dark mode, Inter font |
| Recipe UI | Vanilla JS component via `st.components.v1.html` |

---

## Book Series

**The Hunger Game Is Rigged** — available on Amazon KDP.

Get both books + Full AI Access for **$22.50** → [Amazon](https://www.amazon.com)
