# 🏗️ SiteWatch AI — AI-Powered Construction Intelligence & Risk Mitigation

SiteWatch AI is the ultimate mission control and auditing platform for modern construction sites. Powered by **Gemini 3.1 Flash Lite** via the **AIML API**, it leverages state-of-the-art multi-agent AI systems to detect safety violations in site photos, forecast project schedule delays and cost overruns, and generate production-ready executive PDF audit reports in seconds.

---

## 🌟 Core Modules & Agent Capabilities

### 👁️ 1. Vision Guardian (Photo Audit Agent)
Analyzes construction site photos to evaluate overall safety, estimate build progress, and automatically log safety violations.
* **Safety Violations Logging:** Instantly detects missing Personal Protective Equipment (PPE) like helmets or high-vis vests, unsafe scaffoldings, and hazardous workspace behaviors.
* **Progress Tracking:** Provides a high-fidelity progress percentage estimate of the site build status.
* **Intelligent Scorecards:** Outputs an overall safety and confidence score.

### 📅 2. Schedule Oracle (Risk Analysis Agent)
Processes project schedule worksheets (`.xlsx` or `.csv` files) in tandem with recent Vision findings to run advanced timeline simulation algorithms.
* **Delay Probability:** Computes the likelihood of timeline deviation using historical data and actual progress inputs.
* **Cost Overrun Forecast:** Provides a currency-based estimation of potential budget inflation.
* **Drift Index:** Identifies cumulative baseline slippage in days.
* **Strategic Actions:** Generates AI-engineered corrective strategies and risk mitigations.

### 📄 3. Audit Automator (Report Agent)
Synthesizes Vision audits, schedule risk data, and project contexts into complete, executive-level summaries.
* **Outlook Forecasting:** Generates comprehensive analyses for both budget and timeline status.
* **Action Plans:** Outputs a sequential list of critical corrective actions to address issues.

---

## 🛠️ Technical Architecture

SiteWatch AI is built using a modern, fast, and high-performance stack:

### Frontend (Client-Side)
* **Core:** React 19, TypeScript, Vite
* **Styling & UI:** Tailwind CSS, Shadcn UI, Motion (Framer Motion)
* **Visuals & Charts:** Recharts (responsive prediction/risk matrix visualization)
* **Utilities:** `xlsx` (Excel schedule parsing), `papaparse` (CSV schedule parsing), `jspdf` (Client-side PDF report compilation)

### Backend (Server-Side)
* **Core:** Node.js, Express, `tsx` (TypeScript Execution)
* **AI Core:** OpenAI Node.js SDK configured for the **AIML API Gateway**
* **Active LLM:** **`gemini-3.1-flash-lite`** (for high-frequency, cost-effective vision analysis and structured outputs)
* **Data Guarantee:** Enforced **Structured Outputs (`json_schema` with `strict: true`)** to ensure seamless backend-to-frontend payload formatting.

---

## 📂 Project Structure

```
sitewatch-ai/
├── dist/                     # Compiled production bundles
├── src/                      # Client-side React Application
│   ├── components/
│   │   ├── layout/           # Global dashboard layout & sidebar status
│   │   └── ui/               # Core design system tokens (shadcn/Radix components)
│   ├── context/              # React Context for global state (ProjectContext.tsx)
│   ├── lib/                  # Frontend utilities & API endpoints (api.ts)
│   ├── pages/                # Page views (Dashboard, UploadCenter, RiskAnalytics, ReportsPage)
│   ├── App.tsx               # Main routing & layout wrapper
│   ├── index.css             # Main styling, base design system, & animations
│   └── main.tsx              # React mounting root
├── .env                      # API keys & configurations
├── components.json           # Shadcn UI configuration
├── package.json              # Script runners, dependencies, and devDependencies
├── server.ts                 # Express Backend Server (AI middleware routes)
├── tsconfig.json             # TypeScript compiler rules
└── vite.config.ts            # Vite bundler options & environment mappings
```

---

## 🚀 Installation & Local Setup

Follow these simple steps to run SiteWatch AI on your local machine:

### Prerequisites
* **Node.js** (v18.0.0 or higher recommended)
* **NPM** (v9.0.0 or higher)

### 1. Clone & Navigate
Clone your project repository and open it in a terminal:
```bash
cd sitewatch-ai
```

### 2. Install Dependencies
Install all required client and server dependencies:
```bash
npm install
```

### 3. Environment Variables Configuration
Create a `.env` file in the root directory (or rename `.env.example` to `.env`):
```env
AIMLAPI_KEY="YOUR_AIML_API_KEY_HERE"
APP_URL="http://localhost:3000"
```
*(Replace `YOUR_AIML_API_KEY_HERE` with your active AIML API key).*

---

## 💻 Running the Application

### Development Mode
Start both the Vite development server and the Express backend simultaneously:
```bash
npm run dev
```
Once started, open your browser and navigate to:
👉 **[http://localhost:3000](http://localhost:3000)**

### Production Build
To package and compile the application for production deployment:
```bash
# Clean & compile frontend assets and bundle the server script
npm run build

# Start the optimized production server
npm run start
```

---

## 🤖 API Integrations Detail

SiteWatch AI exposes three core Express backend API routes that process requests via the **AIML API Gateway**:

1. **`POST /api/analyze-photo`**
   * **Input:** Base64 encoded image string + prompt instructions.
   * **Processing:** Passes the image to `gemini-3.1-flash-lite` and performs complex structural object classification.
   * **Output:** Returns a validated safety audit report.

2. **`POST /api/analyze-risk`**
   * **Input:** Parsed schedule JSON data + previous Vision findings.
   * **Processing:** Computes delay probabilities, budget deviation costs, and risk indices.
   * **Output:** Returns a detailed risk-assessment payload.

3. **`POST /api/generate-report-data`**
   * **Input:** Combined Vision audit and Risk results.
   * **Processing:** Formulates executive summaries and timeline/budget outlooks.
   * **Output:** Returns executive summary data blocks.
