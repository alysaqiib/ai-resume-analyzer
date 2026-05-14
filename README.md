# AI Resume Analyzer

AI-powered Resume Analyzer built with Streamlit for MCW HITEC University (AI Project Making - Task 8).

## Features Implemented

- Resume upload (PDF and DOCX) with text extraction and preview
- AI-based skill extraction by category (Programming, Tools, Soft Skills, Other)
- Job match percentage with progress bar
- Missing skills with why each skill matters
- ATS score estimation with breakdown and improvement tips
- Voice feedback (gTTS)
- Interview question generation (Technical, Behavioral, Role-specific)
- Resume rewrite suggestions (original vs improved)
- Keyword density checker with chart
- Tone and language analyzer
- Salary estimator
- Multi-job comparison (up to 3 JDs)
- PDF report export
- **NEW**: API key testing button to validate environment config before analysis
- **NEW**: Better error messages with solutions
- **NEW**: Model selection dropdown with working models only
 - **NEW**: App locked to Gemini `gemini-2.5-flash` for consistent behavior

## Project Files

- main.py: Streamlit app
- .env: Local API key configuration
- requirements.txt: Python dependencies

## Prerequisites

- Python 3.10+ recommended
- Internet connection (for AI APIs and gTTS)
- A valid API key for either:
  - Gemini (Google AI Studio)
  - OpenAI

## Installation

1. Open terminal in the project folder.
2. Create virtual environment (recommended):

Windows (PowerShell):
```
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Windows (CMD):
```
python -m venv .venv
.venv\Scripts\activate.bat
```

3. Install dependencies:
```
pip install -r requirements.txt
```

## API Key Setup (Choose one)

### Option A: Gemini (FREE - Recommended)

1. Go to https://aistudio.google.com/
2. Click "Get API Key" → "Create API Key in new project"
3. Copy the generated key
4. Create a local `.env` file in the project folder with:
```
GEMINI_API_KEY=your_actual_key_here
```
5. In the app sidebar:
   - Model and provider are fixed to `Gemini` / `gemini-2.5-flash`.
   - Ensure your `GEMINI_API_KEY` is set in the `.env` file and the sidebar shows the key-loaded indicator.

### Option B: OpenAI

1. Go to https://platform.openai.com/api/keys
2. Create new secret key (you can only see it once!)
3. Copy the key
4. Create a local `.env` file in the project folder with:
```
OPENAI_API_KEY=your_actual_key_here
```
5. In the app sidebar:
   - Note: this project is locked to Gemini by default; OpenAI keys are supported only if you modify the app.

### Alternative: Set API key in terminal (optional):

Windows (CMD):
```
set GEMINI_API_KEY=your_actual_key_here
```

Windows (PowerShell):
```
$env:GEMINI_API_KEY="your_actual_key_here"
```

Then run the app - the key auto-loads from `.env`.

## Run the App

```
streamlit run main.py
```

Then open the local URL shown in terminal (usually http://localhost:8501).

## Usage Flow

1. Go to **Upload & Analyze** tab
2. Upload resume (PDF or DOCX)
3. Paste a job description
4. In sidebar:
   - Model and provider are fixed to `Gemini` / `gemini-2.5-flash`
   - API key auto-loads from `.env`; ensure the sidebar indicates the key is loaded before analysis
5. Click "Run Full Analysis"
6. Explore all generated sections and charts
7. Optional: Use **Multi-Job Comparison** tab to compare 3 jobs
8. Download report from **Export Report** tab

## Available Models

### Gemini (Free tier available)
- `gemini-2.0-flash` ⭐ (Fastest)
- `gemini-1.5-pro` (Slower but better)
- `gemini-1.5-flash` (Fallback)
- `gemini-pro` (Legacy)

### OpenAI (Paid)
- `gpt-4o-mini` ⭐ (Cheapest, good quality)
- `gpt-4-turbo` (More expensive)
- `gpt-3.5-turbo` (Legacy)

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **404 Model Not Found** | Select different model from dropdown in sidebar. Start with first option. |
| **Invalid API Key** | 1) Copy key exactly (no spaces). 2) Use correct provider (Gemini key ≠ OpenAI key). |
| **"streamlit: command not found"** | Activate virtual env: `.venv\Scripts\activate.bat` |
| **Module not found** | Run: `pip install -r requirements.txt` again |
| **Empty resume parsing** | Make sure PDF is text-based, not scanned image. Try a different resume. |
| **Audio not generating** | Ensure internet is on (gTTS needs it). Check output sound volume. |
| **App won't start** | 1) Check Python 3.10+: `python --version`. 2) Activate venv. 3) Run `pip install -r requirements.txt` |
| **Analysis hangs** | AI can take 30-60 seconds. Wait, or check internet connection. |

## New Features in Updated Version

✅ **API Key Status Indicator** - Green ✓ shows key is loaded from `.env`

✅ **API Key Status Indicator** - Green ✓ shows key is loaded from `.env`

✅ **Fixed Model** - App uses `gemini-2.5-flash` for consistent behavior

✅ **Better Error Messages** - Tells you exactly what's wrong and how to fix it

✅ **Improved UI** - Settings header with gear icon, cleaner sidebar layout

## Tips

- **First time slow?** AI takes 30-60 seconds for full analysis—normal.
- **Keep key private** → Never commit your `.env` file to GitHub.
- **Free tier?** Use Gemini (free) or OpenAI's free trial credits.
- **Test first** → Ensure key is set in `.env` and the sidebar shows the loaded indicator before submitting a long analysis.
- **Want faster?** Use `gpt-4o-mini` (cheaper/faster than `gpt-4-turbo`).

## Deactivate Virtual Environment (When Done)
```
deactivate
```

---

**Issues?** Check the troubleshooting table above. For Gemini API keys, visit aistudio.google.com.

