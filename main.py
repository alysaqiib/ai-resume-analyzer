import io
import json
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import fitz
import pandas as pd
import plotly.express as px
import streamlit as st
from docx import Document
from gtts import gTTS
from openai import OpenAI
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

try:
	import google.generativeai as genai
except ImportError:
	genai = None


def load_env_file(env_path: Path | None = None) -> None:
	# Load local .env values without requiring extra dependencies.
	path = env_path or Path(__file__).with_name(".env")
	if not path.exists():
		return

	for raw_line in path.read_text(encoding="utf-8").splitlines():
		line = raw_line.strip()
		if not line or line.startswith("#"):
			continue
		if line.startswith("export "):
			line = line[len("export "):].strip()
		if "=" not in line:
			continue
		key, value = line.split("=", 1)
		key = key.strip()
		value = value.strip().strip('"').strip("'")
		if key and key not in os.environ:
			os.environ[key] = value


load_env_file()

# Valid model configurations
GEMINI_MODELS = [
	"gemini-2.0-flash",
	"gemini-1.5-pro",
	"gemini-1.5-flash",
	"gemini-pro",
]
OPENAI_MODELS = [
	"gpt-4o-mini",
	"gpt-4-turbo",
	"gpt-3.5-turbo",
]

# Priority order for free-tier-friendly Gemini options.
GEMINI_MODEL_PRIORITY = [
	"gemini-2.0-flash",
	"gemini-1.5-flash",
	"gemini-1.5-pro",
	"gemini-pro",
]


# Streamlit page configuration.
st.set_page_config(
	page_title="AI Resume Analyzer",
	page_icon=":bar_chart:",
	layout="wide",
)


# Basic stopwords for keyword density checks.
STOPWORDS = {
	"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
	"he", "in", "is", "it", "its", "of", "on", "or", "that", "the", "to",
	"was", "were", "will", "with", "you", "your", "we", "our", "this", "those",
	"these", "they", "their", "them", "i", "me", "my", "mine", "about", "into",
	"over", "under", "after", "before", "during", "using", "use", "must", "should",
	"required", "preferred", "plus", "role", "job", "candidate", "experience",
}


def inject_styles() -> None:
	# Custom modern UI styling. Reads `st.session_state['theme']` to pick colors.
	theme = st.session_state.get("theme", "dark")
	# Custom modern UI styling.
	st.markdown(
		"""
		<style>
			@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

			:root {
				/* Default to dark theme variables - will be overridden for light below */
				--bg-a: #071426;
				--bg-b: #06393a;
				--bg-c: #f6fbfb;
				--ink: #eaf6f5;
				--muted: #9fb4bf;
				--good: #17b890;
				--avg: #e6a33f;
				--bad: #e05a4f;
				--brand: #06b6b4;
				--brand-2: #028488;
				--card: rgba(255,255,255,0.04);
			}

			/* Light theme overrides */
			.theme-light :root {
				--bg-a: #f3f7f9;
				--bg-b: #eaf3f4;
				--bg-c: #ffffff;
				--ink: #0f2a2b;
				--muted: #546b6d;
				--good: #0f9d78;
				--avg: #b37522;
				--bad: #b33a32;
				--brand: #0ea5a4;
				--brand-2: #028488;
				--card: rgba(10,20,20,0.04);
			}

			.stApp {
				background:
					radial-gradient(circle at 10% 8%, rgba(255, 184, 103, 0.26), transparent 34%),
					radial-gradient(circle at 88% 14%, rgba(70, 145, 255, 0.22), transparent 38%),
					linear-gradient(150deg, var(--bg-a), var(--bg-b) 55%, var(--bg-c));
				color: var(--ink);
				font-family: 'IBM Plex Sans', sans-serif;
			}

			.main .block-container {
				padding-top: 1.4rem;
				padding-bottom: 2.2rem;
				max-width: 1220px;
			}

			h1, h2, h3 {
				font-family: 'Space Grotesk', sans-serif;
				letter-spacing: 0.2px;
			}

			.hero {
				background: linear-gradient(120deg, rgba(6,57,58,0.96), rgba(2,132,136,0.9));
				color: var(--ink);
				padding: 22px 24px;
				border-radius: 18px;
				box-shadow: 0 18px 40px rgba(2,24,28,0.6);
				margin-bottom: 14px;
				border: 1px solid rgba(255,255,255,0.04);
			}

			.hero h1 {
				font-size: clamp(1.8rem, 2.2vw, 2.5rem);
				margin: 0;
				line-height: 1.12;
			}

			.hero p {
				margin: 8px 0 0 0;
				opacity: 0.95;
				font-size: 1.02rem;
			}

			.hero-row {
				display: flex;
				gap: 10px;
				flex-wrap: wrap;
				margin-top: 12px;
			}

			.pill {
				display: inline-flex;
				align-items: center;
				padding: 7px 12px;
				border-radius: 999px;
				font-size: 0.84rem;
				font-weight: 600;
				border: 1px solid rgba(255,255,255,0.28);
				background: rgba(255,255,255,0.12);
			}

			.glass {
				background: var(--card);
				border: 1px solid rgba(255,255,255,0.06);
				border-radius: 14px;
				padding: 16px 18px;
				box-shadow: 0 10px 30px rgba(2,18,20,0.6);
				animation: floatin 0.45s ease;
				backdrop-filter: blur(6px) saturate(120%);
				margin-bottom: 12px;
			}

			@keyframes floatin {
				from { opacity: 0; transform: translateY(8px); }
				to { opacity: 1; transform: translateY(0); }
			}

			.score-card {
				border-radius: 16px;
				padding: 14px;
				color: white;
				margin-bottom: 8px;
				box-shadow: inset 0 1px 0 rgba(255,255,255,0.2);
			}

			[data-testid="stSidebar"] {
				background: linear-gradient(180deg, rgba(7,20,38,0.96), rgba(6,57,58,0.95));
				border-right: 1px solid rgba(255,255,255,0.04);
				padding-top: 18px;
			}

			[data-testid="stSidebar"] * {
				color: #f2f8ff;
			}

			.stButton > button {
				border-radius: 10px;
				border: none;
				font-weight: 700;
				color: white;
				background: linear-gradient(180deg, var(--brand), var(--brand-2));
				padding: 8px 12px;
				transition: transform .12s ease, box-shadow .12s ease, opacity .12s ease;
			}

			.stButton > button:hover {
				transform: translateY(-2px);
				box-shadow: 0 10px 28px rgba(2,132,136,0.18);
			}

			div[data-baseweb="select"] > div,
			div[data-baseweb="input"] > div,
			div[data-baseweb="textarea"] > div {
				border-radius: 12px !important;
			}

			@media (max-width: 900px) {
				.hero {
					padding: 18px;
				}
			}

			.metric-row {
				display: grid;
				grid-template-columns: repeat(3, minmax(0, 1fr));
				gap: 10px;
				margin-bottom: 10px;
			}

			.metric-chip {
				background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02));
				border: 1px solid rgba(255,255,255,0.04);
				border-radius: 12px;
				padding: 10px 12px;
				box-shadow: 0 8px 26px rgba(2,18,20,0.45);
			}

			.metric-chip strong {
				font-size: 1.08rem;
				display: block;
			}

			.metric-chip span {
				font-size: 0.8rem;
				color: var(--muted);
			}
		</style>
		""",
		unsafe_allow_html=True,
	)


def parse_resume_file(uploaded_file) -> str:
	# Supports PDF and DOCX resume parsing.
	file_bytes = uploaded_file.read()
	filename = uploaded_file.name.lower()

	if filename.endswith(".pdf"):
		doc = fitz.open(stream=file_bytes, filetype="pdf")
		text = "\n".join(page.get_text("text") for page in doc)
		doc.close()
		return text.strip()

	if filename.endswith(".docx"):
		doc = Document(io.BytesIO(file_bytes))
		lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
		return "\n".join(lines).strip()

	raise ValueError("Unsupported file format. Please upload PDF or DOCX.")


def summarize_text(text: str, max_words: int = 140) -> str:
	words = re.findall(r"\S+", text)
	if not words:
		return "No text found in the uploaded resume."
	if len(words) <= max_words:
		return " ".join(words)
	return " ".join(words[:max_words]) + " ..."


def _extract_json_block(raw: str) -> Dict[str, Any]:
	# Tries to recover JSON from model output safely.
	if not raw:
		return {}

	fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
	for item in fenced:
		try:
			return json.loads(item)
		except json.JSONDecodeError:
			pass

	start = raw.find("{")
	end = raw.rfind("}")
	if start != -1 and end != -1 and end > start:
		maybe_json = raw[start:end + 1]
		try:
			return json.loads(maybe_json)
		except json.JSONDecodeError:
			pass
	return {}


def _normalize_gemini_model_name(name: str) -> str:
	if not name:
		return ""
	return name.replace("models/", "").strip()


def detect_key_provider_hint(api_key: str) -> str:
	key = (api_key or "").strip()
	if not key:
		return ""
	if key.startswith("sk-"):
		return "OpenAI-style key detected"
	if key.startswith("AIza"):
		return "Gemini-style key detected"
	return "Unknown key format"


def provider_key_mismatch(provider: str, api_key: str) -> bool:
	key = (api_key or "").strip()
	if not key:
		return False
	if provider == "Gemini" and key.startswith("sk-"):
		return True
	if provider == "OpenAI" and key.startswith("AIza"):
		return True
	return False


def get_provider_api_key(provider: str) -> str:
	if provider == "Gemini":
		return os.getenv("GEMINI_API_KEY", "").strip()
	return os.getenv("OPENAI_API_KEY", "").strip()


def get_available_gemini_models(api_key: str) -> List[str]:
	if genai is None or not api_key.strip():
		return []
	try:
		genai.configure(api_key=api_key)
		available: List[str] = []
		for m in genai.list_models():
			methods = getattr(m, "supported_generation_methods", []) or []
			if "generateContent" in methods:
				available.append(_normalize_gemini_model_name(getattr(m, "name", "")))
		return sorted(list({m for m in available if m}))
	except Exception:
		return []


def ordered_gemini_candidates(requested_model: str, api_key: str) -> List[str]:
	requested = _normalize_gemini_model_name(requested_model)
	defaults = [_normalize_gemini_model_name(m) for m in GEMINI_MODEL_PRIORITY]
	known = [_normalize_gemini_model_name(m) for m in GEMINI_MODELS]
	live = get_available_gemini_models(api_key)

	base_order: List[str] = []
	for item in [requested] + defaults + known + live:
		if item and item not in base_order:
			base_order.append(item)

	if live:
		# Keep our preferred order first, then any other live models.
		preferred_live = [m for m in base_order if m in live]
		other_live = [m for m in live if m not in preferred_live]
		return preferred_live + other_live

	return base_order


def call_ai(prompt: str, provider: str, api_key: str, model_name: str, temperature: float = 0.2) -> str:
	# Unified wrapper for Gemini and OpenAI calls.
	if not api_key or not api_key.strip():
		raise ValueError("API key is empty. Please provide a valid key.")
	api_key = api_key.strip()
	
	if provider == "Gemini":
		if genai is None:
			raise RuntimeError("google-generativeai is not installed. Install dependencies first.")
		genai.configure(api_key=api_key)
		requested = "" if model_name.startswith("Auto") else model_name
		candidates = ordered_gemini_candidates(requested, api_key)
		last_error: Exception | None = None

		for candidate in candidates:
			try:
				model = genai.GenerativeModel(candidate)
				resp = model.generate_content(
					prompt,
					generation_config={"temperature": temperature},
				)
				return (resp.text or "").strip()
			except Exception as e:
				error_msg = str(e).lower()
				last_error = e
				# Retry on model-unavailable errors; raise immediately for auth/permission issues.
				if "invalid" in error_msg and "api" in error_msg:
					raise ValueError("Invalid Gemini API key. Check your key and try again.")
				if "permission" in error_msg:
					raise ValueError(f"Gemini access issue: {e}")
				# Handle quota / rate limit specially: try fallback to OpenAI if available
				if "quota" in error_msg or "429" in error_msg or "rate limit" in error_msg:
					openai_key = os.getenv("OPENAI_API_KEY", "")
					if openai_key:
						# Attempt a quick OpenAI fallback using available models
						for fallback_model in OPENAI_MODELS:
							try:
								client = OpenAI(api_key=openai_key)
								resp = client.chat.completions.create(
									model=fallback_model,
									temperature=temperature,
									messages=[
										{"role": "system", "content": "You are an expert resume analysis assistant. Return strictly useful output."},
										{"role": "user", "content": prompt},
									],
								)
								return (resp.choices[0].message.content or "").strip()
							except Exception:
								continue
					# If fallback not possible, raise instructive message
					raise ValueError(
						"Gemini quota exceeded (HTTP 429).\n"
						"Options:\n"
						"  1) Wait for quota reset or upgrade your Google AI Studio plan.\n"
						"  2) Create a new API key/project in Google AI Studio and try again.\n"
						"  3) Provide an OpenAI API key (OPENAI_API_KEY) to let the app auto-fallback.\n"
						f"Original error: {e}"
					)
				if "404" in error_msg or "not found" in error_msg or "unsupported" in error_msg:
					continue
				# For transient/other errors, keep trying remaining candidates once.
				continue

		available = get_available_gemini_models(api_key)
		if available:
			raise ValueError(
				f"No working Gemini model from selection. Available for your key: {', '.join(available[:8])}. "
				f"Last error: {last_error}"
			)
		raise ValueError(
			"No Gemini generateContent model is available for this API key/project. "
			"Create a new key in Google AI Studio and retry."
		)

	try:
		if model_name.startswith("Auto"):
			for fallback_model in OPENAI_MODELS:
				try:
					client = OpenAI(api_key=api_key)
					resp = client.chat.completions.create(
						model=fallback_model,
						temperature=temperature,
						messages=[
							{"role": "system", "content": "You are an expert resume analysis assistant. Return strictly useful output."},
							{"role": "user", "content": prompt},
						],
					)
					return (resp.choices[0].message.content or "").strip()
				except Exception:
					continue
			raise ValueError("No OpenAI model is accessible for this key. Try a different key or model.")

		client = OpenAI(api_key=api_key)
		resp = client.chat.completions.create(
			model=model_name,
			temperature=temperature,
			messages=[
				{"role": "system", "content": "You are an expert resume analysis assistant. Return strictly useful output."},
				{"role": "user", "content": prompt},
			],
		)
		return (resp.choices[0].message.content or "").strip()
	except Exception as e:
		error_msg = str(e)
		if "api_key" in error_msg.lower() or "auth" in error_msg.lower():
			raise ValueError(f"Invalid OpenAI API key. Check your key and try again.")
		if "model" in error_msg.lower():
			raise ValueError(f"Model '{model_name}' not available. Try: {', '.join(OPENAI_MODELS[:2])}. Error: {e}")
		raise


def score_color(score: int) -> str:
	if score >= 75:
		return "#1f8b4c"
	if score >= 50:
		return "#b37800"
	return "#b12d2d"


def render_score_card(title: str, score: int, subtitle: str = "") -> None:
	color = score_color(score)
	st.markdown(
		f"""
		<div class="score-card" style="background:{color}">
			<h4 style="margin:0">{title}</h4>
			<h2 style="margin:6px 0">{score}/100</h2>
			<p style="margin:0;opacity:0.95">{subtitle}</p>
		</div>
		""",
		unsafe_allow_html=True,
	)


def safe_int(value: Any, default: int = 0) -> int:
	try:
		n = int(round(float(value)))
	except (TypeError, ValueError):
		return default
	return max(0, min(100, n))


def fallback_match_percentage(resume_text: str, jd_text: str) -> int:
	res_words = set(re.findall(r"[a-zA-Z][a-zA-Z+.#-]{1,}", resume_text.lower()))
	jd_words = set(re.findall(r"[a-zA-Z][a-zA-Z+.#-]{1,}", jd_text.lower())) - STOPWORDS
	if not jd_words:
		return 0
	overlap = len(res_words & jd_words)
	return int((overlap / len(jd_words)) * 100)


def extract_top_keywords(text: str, top_n: int = 20) -> List[str]:
	words = re.findall(r"[a-zA-Z][a-zA-Z+.#-]{2,}", text.lower())
	words = [w for w in words if w not in STOPWORDS]
	return [w for w, _ in Counter(words).most_common(top_n)]


def keyword_density_table(resume_text: str, keywords: List[str]) -> pd.DataFrame:
	# Builds keyword frequency and density table.
	tokens = re.findall(r"[a-zA-Z][a-zA-Z+.#-]{1,}", resume_text.lower())
	total = max(len(tokens), 1)
	counter = Counter(tokens)
	rows = []
	for kw in keywords:
		freq = counter.get(kw.lower(), 0)
		rows.append(
			{
				"Keyword": kw,
				"Count": freq,
				"Density (%)": round((freq / total) * 100, 2),
			}
		)
	return pd.DataFrame(rows).sort_values(["Count", "Density (%)"], ascending=False)


def build_main_analysis_prompt(resume_text: str, jd_text: str) -> str:
	return f"""
Analyze the resume against the job description and return ONLY valid JSON.
Do not include markdown, comments, or extra text.

JSON schema:
{{
  "skills": {{
	"programming": ["..."],
	"tools": ["..."],
	"soft_skills": ["..."],
	"other": ["..."]
  }},
  "job_match": {{"percentage": 0, "summary": "..."}},
  "missing_skills": [{{"skill": "...", "why_it_matters": "..."}}],
  "ats": {{
	"overall": 0,
	"keyword_density": 0,
	"formatting": 0,
	"section_presence": 0,
	"readability": 0,
	"tips": ["...", "..."]
  }},
  "feedback_summary": "2-4 lines overall feedback",
  "interview_questions": [
	{{"category": "Technical|Behavioral|Role-specific", "question": "...", "answer_tip": "..."}}
  ],
  "rewrite_suggestions": [
	{{"original": "weak bullet", "improved": "strong bullet", "why_better": "..."}}
  ],
  "tone_language": {{
	"tone": "Formal|Casual|Mixed",
	"voice": "Active|Passive|Mixed",
	"issues": ["..."],
	"improvements": ["..."]
  }},
  "salary_estimate": {{
	"job_title": "...",
	"experience_level": "...",
	"currency": "USD",
	"min": 0,
	"max": 0,
	"reasoning": "..."
  }},
  "important_keywords": ["...", "..."]
}}

Resume:
{resume_text[:14000]}

Job Description:
{jd_text[:9000]}
""".strip()


def run_main_analysis(resume_text: str, jd_text: str, provider: str, api_key: str, model_name: str) -> Dict[str, Any]:
	# Runs complete AI analysis for one job description.
	prompt = build_main_analysis_prompt(resume_text, jd_text)
	raw = call_ai(prompt, provider, api_key, model_name, temperature=0.2)
	data = _extract_json_block(raw)

	if not data:
		# Fallback with minimum structure if model output is malformed.
		match = fallback_match_percentage(resume_text, jd_text)
		return {
			"skills": {
				"programming": [],
				"tools": [],
				"soft_skills": [],
				"other": [],
			},
			"job_match": {"percentage": match, "summary": "Heuristic match based on keyword overlap."},
			"missing_skills": [],
			"ats": {
				"overall": max(45, match),
				"keyword_density": max(40, match - 5),
				"formatting": 60,
				"section_presence": 55,
				"readability": 65,
				"tips": [
					"Add missing job-specific keywords naturally in experience bullets.",
					"Ensure clear sections: Summary, Skills, Experience, Projects, Education.",
				],
			},
			"feedback_summary": "AI response could not be parsed. Showing partial heuristic results.",
			"interview_questions": [],
			"rewrite_suggestions": [],
			"tone_language": {"tone": "Mixed", "voice": "Mixed", "issues": [], "improvements": []},
			"salary_estimate": {
				"job_title": "Not detected",
				"experience_level": "Not detected",
				"currency": "USD",
				"min": 0,
				"max": 0,
				"reasoning": "Insufficient structured AI output.",
			},
			"important_keywords": extract_top_keywords(jd_text, top_n=15),
		}

	data.setdefault("skills", {})
	data.setdefault("job_match", {})
	data.setdefault("ats", {})
	data.setdefault("missing_skills", [])
	data.setdefault("interview_questions", [])
	data.setdefault("rewrite_suggestions", [])
	data.setdefault("tone_language", {})
	data.setdefault("salary_estimate", {})
	data.setdefault("important_keywords", extract_top_keywords(jd_text, top_n=15))

	data["job_match"]["percentage"] = safe_int(data["job_match"].get("percentage", fallback_match_percentage(resume_text, jd_text)))
	data["ats"]["overall"] = safe_int(data["ats"].get("overall", 0))
	data["ats"]["keyword_density"] = safe_int(data["ats"].get("keyword_density", 0))
	data["ats"]["formatting"] = safe_int(data["ats"].get("formatting", 0))
	data["ats"]["section_presence"] = safe_int(data["ats"].get("section_presence", 0))
	data["ats"]["readability"] = safe_int(data["ats"].get("readability", 0))
	return data


def run_match_for_many_jobs(
	resume_text: str,
	jobs: List[str],
	provider: str,
	api_key: str,
	model_name: str,
) -> List[Dict[str, Any]]:
	# Extra feature: compare match percentages across up to 3 jobs.
	rows: List[Dict[str, Any]] = []
	for idx, jd in enumerate(jobs, start=1):
		if not jd.strip():
			continue
		prompt = f"""
Return JSON only with this schema: {{"percentage": 0, "summary": "one sentence"}}.
Compare this resume against the job description and estimate match.

Resume:
{resume_text[:9000]}

Job Description:
{jd[:5000]}
""".strip()
		percentage = fallback_match_percentage(resume_text, jd)
		summary = "Heuristic keyword-overlap estimate."
		try:
			raw = call_ai(prompt, provider, api_key, model_name, temperature=0.1)
			parsed = _extract_json_block(raw)
			if parsed:
				percentage = safe_int(parsed.get("percentage", percentage))
				summary = str(parsed.get("summary", summary))
		except Exception:
			pass

		rows.append(
			{
				"Job #": f"Job {idx}",
				"Match %": percentage,
				"Verdict": "Strong" if percentage >= 75 else "Moderate" if percentage >= 50 else "Weak",
				"Note": summary,
			}
		)
	return rows


def feedback_audio_bytes(text: str) -> bytes:
	tts = gTTS(text=text, lang="en")
	buf = io.BytesIO()
	tts.write_to_fp(buf)
	buf.seek(0)
	return buf.read()


def _draw_wrapped_line_block(c: canvas.Canvas, text: str, x: float, y: float, max_chars: int = 95, step: int = 14) -> float:
	lines: List[str] = []
	for paragraph in text.split("\n"):
		words = paragraph.split()
		if not words:
			lines.append("")
			continue
		current = words[0]
		for w in words[1:]:
			trial = f"{current} {w}"
			if len(trial) > max_chars:
				lines.append(current)
				current = w
			else:
				current = trial
		lines.append(current)

	for line in lines:
		if y < 50:
			c.showPage()
			c.setFont("Helvetica", 10)
			y = 800
		c.drawString(x, y, line)
		y -= step
	return y


def build_pdf_report(
	candidate_name: str,
	analysis: Dict[str, Any],
	keyword_df: pd.DataFrame,
	multi_rows: List[Dict[str, Any]],
) -> bytes:
	# Builds exportable project report PDF.
	buf = io.BytesIO()
	c = canvas.Canvas(buf, pagesize=A4)
	y = 810

	c.setTitle("AI Resume Analyzer Report")
	c.setFont("Helvetica-Bold", 16)
	c.drawString(50, y, "AI Resume Analyzer - Full Report")
	y -= 24

	c.setFont("Helvetica", 10)
	c.drawString(50, y, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
	y -= 14
	c.drawString(50, y, f"Candidate File: {candidate_name}")
	y -= 24

	c.setFont("Helvetica-Bold", 12)
	c.drawString(50, y, "Core Scores")
	y -= 18
	c.setFont("Helvetica", 10)
	c.drawString(50, y, f"Job Match: {analysis.get('job_match', {}).get('percentage', 0)}%")
	y -= 14
	c.drawString(50, y, f"ATS Score: {analysis.get('ats', {}).get('overall', 0)}/100")
	y -= 20

	c.setFont("Helvetica-Bold", 12)
	c.drawString(50, y, "Skills")
	y -= 18
	skills = analysis.get("skills", {})
	for cat in ["programming", "tools", "soft_skills", "other"]:
		values = ", ".join(skills.get(cat, [])[:15]) if isinstance(skills.get(cat), list) else ""
		c.setFont("Helvetica-Bold", 10)
		c.drawString(50, y, f"{cat.replace('_', ' ').title()}: ")
		c.setFont("Helvetica", 10)
		y = _draw_wrapped_line_block(c, values or "None listed", 170, y)
		y -= 6

	c.setFont("Helvetica-Bold", 12)
	c.drawString(50, y, "Missing Skills")
	y -= 18
	c.setFont("Helvetica", 10)
	missing = analysis.get("missing_skills", [])[:10]
	if not missing:
		c.drawString(50, y, "No major missing skills were identified.")
		y -= 14
	else:
		for item in missing:
			line = f"- {item.get('skill', '')}: {item.get('why_it_matters', '')}"
			y = _draw_wrapped_line_block(c, line, 50, y)

	y -= 10
	c.setFont("Helvetica-Bold", 12)
	c.drawString(50, y, "ATS Improvement Tips")
	y -= 18
	tips = analysis.get("ats", {}).get("tips", [])[:8]
	for t in tips:
		y = _draw_wrapped_line_block(c, f"- {t}", 50, y)

	y -= 10
	c.setFont("Helvetica-Bold", 12)
	c.drawString(50, y, "Interview Questions")
	y -= 18
	questions = analysis.get("interview_questions", [])[:8]
	for q in questions:
		block = f"[{q.get('category', 'General')}] {q.get('question', '')} | Tip: {q.get('answer_tip', '')}"
		y = _draw_wrapped_line_block(c, block, 50, y)

	if y < 180:
		c.showPage()
		c.setFont("Helvetica", 10)
		y = 800

	c.setFont("Helvetica-Bold", 12)
	c.drawString(50, y, "Keyword Density Snapshot")
	y -= 18
	c.setFont("Helvetica", 10)
	top_rows = keyword_df.head(12).to_dict("records") if not keyword_df.empty else []
	for row in top_rows:
		c.drawString(50, y, f"- {row['Keyword']}: {row['Count']} ({row['Density (%)']}%)")
		y -= 14

	y -= 8
	c.setFont("Helvetica-Bold", 12)
	c.drawString(50, y, "Multi-Job Comparison")
	y -= 18
	c.setFont("Helvetica", 10)
	if not multi_rows:
		c.drawString(50, y, "No additional job descriptions provided.")
	else:
		for r in multi_rows:
			c.drawString(50, y, f"- {r['Job #']}: {r['Match %']}% ({r['Verdict']})")
			y -= 14

	c.save()
	return buf.getvalue()


def init_state() -> None:
	# Initializes app-level session state values.
	defaults = {
		"resume_text": "",
		"resume_name": "",
		"analysis": None,
		"keyword_df": pd.DataFrame(),
		"multi_job_rows": [],
	}
	for k, v in defaults.items():
		if k not in st.session_state:
			st.session_state[k] = v


def render_skill_tags(title: str, items: List[str]) -> None:
	st.markdown(f"**{title}**")
	if not items:
		st.caption("No items detected.")
		return
	line = " ".join([f"`{x}`" for x in items])
	st.markdown(line)


def render_hero(resume_loaded: bool, has_analysis: bool, match_score: int, ats_score: int) -> None:
	resume_state = "Resume parsed" if resume_loaded else "Resume not uploaded"
	analysis_state = "Analysis ready" if has_analysis else "Awaiting analysis"

	st.markdown(
		f"""
		<div class="hero">
			<h1>AI Resume Analyzer Studio</h1>
			<p>Upload resume, align with target roles, and export an interview-ready improvement report.</p>
			<div class="hero-row">
				<div class="pill">{resume_state}</div>
				<div class="pill">{analysis_state}</div>
				<div class="pill">Match {match_score}%</div>
				<div class="pill">ATS {ats_score}/100</div>
			</div>
		</div>
		""",
		unsafe_allow_html=True,
	)


def render_top_metrics(resume_text: str, analysis: Dict[str, Any]) -> None:
	resume_chars = len(resume_text.strip()) if resume_text else 0
	missing_count = len(analysis.get("missing_skills", [])) if analysis else 0
	interview_count = len(analysis.get("interview_questions", [])) if analysis else 0

	st.markdown(
		f"""
		<div class="metric-row">
			<div class="metric-chip"><strong>{resume_chars:,}</strong><span>Resume Characters Parsed</span></div>
			<div class="metric-chip"><strong>{missing_count}</strong><span>Missing Skills Identified</span></div>
			<div class="metric-chip"><strong>{interview_count}</strong><span>Interview Questions Generated</span></div>
		</div>
		""",
		unsafe_allow_html=True,
	)


def main() -> None:
	# Main Streamlit application layout and logic.
	init_state()

	current_analysis = st.session_state.get("analysis") or {}
	match_score = safe_int(current_analysis.get("job_match", {}).get("percentage", 0))
	ats_score = safe_int(current_analysis.get("ats", {}).get("overall", 0))
	render_hero(
		resume_loaded=bool(st.session_state.get("resume_text", "").strip()),
		has_analysis=bool(st.session_state.get("analysis")),
		match_score=match_score,
		ats_score=ats_score,
	)
	render_top_metrics(st.session_state.get("resume_text", ""), current_analysis)
	st.caption("MCW HITEC University | AI Project Making (Task 8)")

	with st.sidebar:
		# Theme selector
		st.markdown("**Theme**")
		choice = st.radio("Appearance", ["Teal Dark", "Soft Light"], index=0, key="_theme_radio")
		st.session_state["theme"] = "dark" if choice == "Teal Dark" else "light"

		st.header("⚙️ Settings")
		# App is fixed to Gemini provider and gemini-2.5-flash model per user request
		provider = "Gemini"
		st.markdown("**AI Provider:** Gemini")

		# Load API key from environment/.env
		api_key = get_provider_api_key(provider)

		model_name = "gemini-2.5-flash"
		st.markdown(f"**Model:** {model_name} (fixed)")

		if api_key.strip():
			st.success("✓ API key loaded from environment", icon="✅")
		else:
			st.warning("⚠ No API key provided", icon="⚠️")
			st.caption("Add GEMINI_API_KEY to the local .env file.")

		if api_key.strip():
			st.caption(f"Key hint: {detect_key_provider_hint(api_key)}")
		
		# API guidance (Test button removed)
		st.markdown("**API Access**")
		st.info(
			"This app uses the Gemini provider (gemini-2.5-flash).\n\n"
			"Add your Gemini key to the project .env file as `GEMINI_API_KEY=...`.\n\n"
			"Get a key at: aistudio.google.com (create project → API keys).\n\n"
			"Do not commit your .env file to version control."
		)

		# Inject styles after sidebar so theme selection takes effect immediately
		inject_styles()

		st.divider()
		page = st.radio(
			"Navigation",
			[
				"Upload & Analyze",
				"Multi-Job Comparison",
				"Export Report",
				"Run Instructions",
			],
		)

	if page == "Upload & Analyze":
		left, right = st.columns([1.05, 1], gap="large")

		with left:
			st.markdown('<div class="glass">', unsafe_allow_html=True)
			st.subheader("1) Upload Resume")
			uploaded = st.file_uploader("Upload PDF or DOCX", type=["pdf", "docx"])

			if uploaded is not None:
				try:
					parsed_text = parse_resume_file(uploaded)
					st.session_state["resume_text"] = parsed_text
					st.session_state["resume_name"] = uploaded.name
					st.success("Resume parsed successfully.")

					st.markdown("**Parsed Text Preview**")
					st.text_area("Preview", value=summarize_text(parsed_text), height=180, label_visibility="collapsed")
					st.caption(f"Total characters extracted: {len(parsed_text)}")
				except Exception as ex:
					st.error(f"Failed to parse resume: {ex}")

			st.subheader("2) Paste Job Description")
			jd_text = st.text_area("Job Description", height=220, placeholder="Paste job description here...")

			analyze_btn = st.button("Run Full Analysis", type="primary", use_container_width=True)
			st.markdown('</div>', unsafe_allow_html=True)

			if analyze_btn:
				if not st.session_state["resume_text"].strip():
					st.warning("Please upload a resume first.")
				elif not jd_text.strip():
					st.warning("Please paste a job description.")
				elif not api_key.strip():
					st.warning("Please add the provider API key to .env first.")
				else:
					with st.spinner("Analyzing resume with AI..."):
						try:
							analysis = run_main_analysis(
								st.session_state["resume_text"],
								jd_text,
								provider,
								api_key,
								model_name,
							)
							keywords = analysis.get("important_keywords") or extract_top_keywords(jd_text, top_n=20)
							keyword_df = keyword_density_table(st.session_state["resume_text"], keywords)

							st.session_state["analysis"] = analysis
							st.session_state["keyword_df"] = keyword_df
							st.success("✅ Analysis completed successfully!")
						except ValueError as ex:
							st.error(f"⚠️ **Configuration Error**: {str(ex)[:200]}")
							st.info("💡 **Solutions**:\\n- Check API key is correct\\n- Try different model from sidebar\\n- Click 'Test API' button to validate")
						except Exception as ex:
							error_text = str(ex)[:250]
							st.error(f"❌ **AI Analysis Failed**: {error_text}")
							if "404" in error_text or "not found" in error_text.lower():
								st.warning("Model not available. Try selecting a different model from the sidebar.")
							else:
								st.info("💡 Try: 1) Test API button 2) Different model 3) Check internet connection")

		with right:
			analysis = st.session_state.get("analysis")
			if not analysis:
				st.info("Run analysis to view ATS score, match %, skills, suggestions, and interview questions.")
			else:
				st.markdown('<div class="glass">', unsafe_allow_html=True)
				st.subheader("3) Match & ATS Overview")
				c1, c2 = st.columns(2)
				with c1:
					render_score_card("Job Match", safe_int(analysis.get("job_match", {}).get("percentage", 0)), "Resume vs Job Description")
				with c2:
					render_score_card("ATS Score", safe_int(analysis.get("ats", {}).get("overall", 0)), "Estimated ATS compatibility")

				st.progress(safe_int(analysis.get("job_match", {}).get("percentage", 0)) / 100, text="Job Match Progress")
				st.progress(safe_int(analysis.get("ats", {}).get("overall", 0)) / 100, text="ATS Progress")

				st.markdown("**AI Summary Feedback**")
				st.write(analysis.get("feedback_summary", "No summary available."))

				if st.button("Listen to Feedback"):
					try:
						audio = feedback_audio_bytes(analysis.get("feedback_summary", "No summary available."))
						st.audio(audio, format="audio/mp3")
					except Exception as ex:
						st.warning("⚠️ Audio generation unavailable (needs internet). Check connection and try again.")

				st.markdown('</div>', unsafe_allow_html=True)
		if analysis:
			a, b = st.columns(2, gap="large")
			with a:
				st.markdown('<div class="glass">', unsafe_allow_html=True)
				st.subheader("4) Skill Extraction")
				skills = analysis.get("skills", {})
				render_skill_tags("Programming", skills.get("programming", []))
				render_skill_tags("Tools", skills.get("tools", []))
				render_skill_tags("Soft Skills", skills.get("soft_skills", []))
				render_skill_tags("Other", skills.get("other", []))
				st.markdown('</div>', unsafe_allow_html=True)

				st.markdown('<div class="glass">', unsafe_allow_html=True)
				st.subheader("5) Missing Skills Suggestions")
				missing = analysis.get("missing_skills", [])
				if not missing:
					st.success("No high-priority skill gaps detected.")
				else:
					for item in missing:
						st.markdown(f"**{item.get('skill', 'Unknown Skill')}**")
						st.write(item.get("why_it_matters", "No explanation."))
				st.markdown('</div>', unsafe_allow_html=True)

				st.markdown('<div class="glass">', unsafe_allow_html=True)
				st.subheader("6) ATS Score Breakdown")
				ats = analysis.get("ats", {})
				for label, key in [
					("Keyword Density", "keyword_density"),
					("Formatting", "formatting"),
					("Section Presence", "section_presence"),
					("Readability", "readability"),
				]:
					val = safe_int(ats.get(key, 0))
					st.write(f"{label}: {val}/100")
					st.progress(val / 100)
				st.markdown("**Tips to Improve ATS Score**")
				for tip in ats.get("tips", []):
					st.write(f"- {tip}")
				st.markdown('</div>', unsafe_allow_html=True)

			with b:
				st.markdown('<div class="glass">', unsafe_allow_html=True)
				st.subheader("7) Interview Questions")
				questions = analysis.get("interview_questions", [])
				if not questions:
					st.info("No interview questions generated.")
				else:
					for q in questions[:10]:
						st.markdown(f"**[{q.get('category', 'General')}] {q.get('question', '')}**")
						st.caption(f"Answer tip: {q.get('answer_tip', '')}")
				st.markdown('</div>', unsafe_allow_html=True)

				st.markdown('<div class="glass">', unsafe_allow_html=True)
				st.subheader("8) Resume Rewrite Suggestions")
				rewrites = analysis.get("rewrite_suggestions", [])
				if not rewrites:
					st.info("No rewrite suggestions generated.")
				else:
					for row in rewrites[:8]:
						c1, c2 = st.columns(2)
						with c1:
							st.markdown("**Original**")
							st.write(row.get("original", ""))
						with c2:
							st.markdown("**Improved**")
							st.write(row.get("improved", ""))
						st.caption(f"Why better: {row.get('why_better', '')}")
				st.markdown('</div>', unsafe_allow_html=True)

				st.markdown('<div class="glass">', unsafe_allow_html=True)
				st.subheader("9) Tone & Language Analyzer")
				tone = analysis.get("tone_language", {})
				st.write(f"Tone: {tone.get('tone', 'Unknown')}")
				st.write(f"Voice: {tone.get('voice', 'Unknown')}")
				issues = tone.get("issues", [])
				improvements = tone.get("improvements", [])
				if issues:
					st.markdown("**Detected Issues**")
					for i in issues:
						st.write(f"- {i}")
				if improvements:
					st.markdown("**Suggested Improvements**")
					for i in improvements:
						st.write(f"- {i}")
				st.markdown('</div>', unsafe_allow_html=True)

				st.markdown('<div class="glass">', unsafe_allow_html=True)
				st.subheader("10) Salary Estimator")
				sal = analysis.get("salary_estimate", {})
				currency = sal.get("currency", "USD")
				st.write(f"Role: {sal.get('job_title', 'Unknown')}")
				st.write(f"Experience Level: {sal.get('experience_level', 'Unknown')}")
				st.write(f"Estimated Range: {currency} {sal.get('min', 0)} - {currency} {sal.get('max', 0)}")
				st.caption(sal.get("reasoning", "No reasoning provided."))
				st.markdown('</div>', unsafe_allow_html=True)

			st.markdown('<div class="glass">', unsafe_allow_html=True)
			st.subheader("11) Keyword Density Checker")
			keyword_df = st.session_state.get("keyword_df", pd.DataFrame())
			if keyword_df.empty:
				st.info("Keyword density table is empty.")
			else:
				st.dataframe(keyword_df, use_container_width=True)
				fig = px.bar(keyword_df.head(15), x="Keyword", y="Count", color="Density (%)", title="Top Keyword Frequency")
				st.plotly_chart(fig, use_container_width=True)
			st.markdown('</div>', unsafe_allow_html=True)

	elif page == "Multi-Job Comparison":
		st.subheader("12) Compare Resume Against Multiple Jobs")
		st.markdown('<div class="glass">', unsafe_allow_html=True)
		st.write("Paste up to 3 job descriptions and compare match percentages.")
		jd1 = st.text_area("Job Description 1", height=140)
		jd2 = st.text_area("Job Description 2", height=140)
		jd3 = st.text_area("Job Description 3", height=140)

		if st.button("Run Multi-Job Comparison", type="primary"):
			resume_text = st.session_state.get("resume_text", "")
			if not resume_text.strip():
				st.warning("Please upload and parse a resume first from Upload & Analyze page.")
			elif not api_key.strip():
					st.warning("Please add the provider API key to .env first.")
			else:
				jobs = [jd1, jd2, jd3]
				with st.spinner("Comparing across job descriptions..."):
					try:
						rows = run_match_for_many_jobs(resume_text, jobs, provider, api_key, model_name)
						st.session_state["multi_job_rows"] = rows
						st.success("✅ Comparison completed!")
					except ValueError as ex:
						st.error(f"⚠️ **Configuration Error**: {str(ex)[:200]}")
					except Exception as ex:
						st.error(f"❌ **Comparison Failed**: {str(ex)[:200]}")

		rows = st.session_state.get("multi_job_rows", [])
		if rows:
			df = pd.DataFrame(rows)
			st.dataframe(df, use_container_width=True)
			fig = px.bar(df, x="Job #", y="Match %", color="Verdict", title="Multi-Job Match Comparison")
			st.plotly_chart(fig, use_container_width=True)
		st.markdown('</div>', unsafe_allow_html=True)

	elif page == "Export Report":
		st.subheader("13) Export Full Report as PDF")
		analysis = st.session_state.get("analysis")
		if not analysis:
			st.info("Please run analysis first from Upload & Analyze page.")
		else:
			pdf_bytes = build_pdf_report(
				candidate_name=st.session_state.get("resume_name", "resume"),
				analysis=analysis,
				keyword_df=st.session_state.get("keyword_df", pd.DataFrame()),
				multi_rows=st.session_state.get("multi_job_rows", []),
			)
			st.download_button(
				label="Download Analysis Report (PDF)",
				data=pdf_bytes,
				file_name="resume_analysis_report.pdf",
				mime="application/pdf",
				use_container_width=True,
			)

	else:
		st.subheader("Run Locally")
		st.markdown("Create a local .env file with GEMINI_API_KEY or OPENAI_API_KEY, then run `streamlit run main.py`.")


if __name__ == "__main__":
	main()
