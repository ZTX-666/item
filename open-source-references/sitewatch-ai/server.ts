import express from "express";
import path from "path";
import { createServer as createViteServer } from "vite";
import { OpenAI } from "openai";
import dotenv from "dotenv";
import { PDFParse } from "pdf-parse";



dotenv.config();

async function startServer() {
  const app = express();
  const PORT = 3000;

  // Initialize AIML API Client (OpenAI compatible)
  const apiKey = process.env.AIMLAPI_KEY;
  if (!apiKey) {
    console.warn("AIMLAPI_KEY is not set. AI features will not work.");
  }
  
  const openai = new OpenAI({
    apiKey: apiKey || "dummy-key",
    baseURL: "https://api.aimlapi.com/v1"
  });

  app.use(express.json({ limit: '50mb' }));

  // API Routes
  app.get("/api/health", (req, res) => {
    res.json({ status: "ok" });
  });

  // Parse PDF
  app.post("/api/parse-pdf", async (req, res) => {
    try {
      const { pdfBase64 } = req.body;
      if (!pdfBase64) return res.status(400).json({ error: "No PDF data provided" });

      const buffer = Buffer.from(pdfBase64.split(",")[1] || pdfBase64, "base64");
      const parser = new PDFParse({ data: buffer });
      const result = await parser.getText();
      const text = result.text;
      await parser.destroy();
      
      res.json({ text });
    } catch (error: any) {
      console.error("PDF Parsing Error:", error);
      res.status(500).json({ error: error.message });
    }
  });

  // 1. Analyze Photo (Vision Agent)
  app.post("/api/analyze-photo", async (req, res) => {
    try {
      const { image, prompt } = req.body;
      if (!image) return res.status(400).json({ error: "No image provided" });

      const imageUrl = image.startsWith("data:") ? image : `data:image/jpeg;base64,${image}`;

      const response = await openai.chat.completions.create({
        model: "gemini-3.1-flash-lite",
        messages: [
          {
            role: "user",
            content: [
              { type: "text", text: prompt || "Analyze this construction site photo for safety violations, progress, and overall site condition. Return a structured JSON response." },
              { type: "image_url", image_url: { url: imageUrl } }
            ]
          }
        ],
        response_format: {
          type: "json_schema",
          json_schema: {
            name: "vision_analysis",
            strict: true,
            schema: {
              type: "object",
              properties: {
                violations: {
                  type: "array",
                  items: {
                    type: "object",
                    properties: {
                      type: { type: "string" },
                      severity: { type: "string" },
                      location: { type: "string" },
                      recommendation: { type: "string" }
                    },
                    required: ["type", "severity", "location", "recommendation"],
                    additionalProperties: false
                  }
                },
                progress_estimate: { type: "number" },
                overall_safety_score: { type: "number" },
                summary: { type: "string" },
                confidence: { type: "number" }
              },
              required: ["violations", "progress_estimate", "overall_safety_score", "summary", "confidence"],
              additionalProperties: false
            }
          }
        }
      });

      const responseText = response.choices[0]?.message?.content || "{}";
      res.json(JSON.parse(responseText));
    } catch (error: any) {
      console.error("AI Analysis Error:", error);
      res.status(500).json({ error: error.message });
    }
  });

  // 2. Analyze Risk (Risk Agent)
  app.post("/api/analyze-risk", async (req, res) => {
    try {
      const { scheduleData, visionResults } = req.body;

      const prompt = `
        Analyze the following construction project data and predict risks.
        Schedule Data: ${JSON.stringify(scheduleData)}
        Vision Analysis Findings: ${JSON.stringify(visionResults)}
        
        Look for timeline deviations, budget risks, and delay probabilities.
        Also determine:
        1. A predicted 'target_end_date' (a string, e.g. "Oct 24, 2026" or calculated end date based on timeline drift).
        2. A predicted 'risk_status' (e.g. "On Track", "Slight Delay", "Critical Delay", "High Risk").
        3. For 'top_risks', return an array of objects containing 'factor' (string), 'severity' ("HIGH" or "MEDIUM" or "LOW"), and 'probability' (number, 0-100).
      `;

      const response = await openai.chat.completions.create({
        model: "gemini-3.1-flash-lite",
        messages: [
          { role: "user", content: prompt }
        ],
        response_format: {
          type: "json_schema",
          json_schema: {
            name: "risk_analysis",
            strict: true,
            schema: {
              type: "object",
              properties: {
                delay_probability: { type: "number" },
                days_behind_schedule: { type: "number" },
                cost_overrun_risk: { type: "number" },
                target_end_date: { type: "string" },
                risk_status: { type: "string" },
                top_risks: {
                  type: "array",
                  items: {
                    type: "object",
                    properties: {
                      factor: { type: "string" },
                      severity: { type: "string" },
                      probability: { type: "number" }
                    },
                    required: ["factor", "severity", "probability"],
                    additionalProperties: false
                  }
                },
                recommended_actions: { type: "array", items: { type: "string" } }
              },
              required: [
                "delay_probability",
                "days_behind_schedule",
                "cost_overrun_risk",
                "target_end_date",
                "risk_status",
                "top_risks",
                "recommended_actions"
              ],
              additionalProperties: false
            }
          }
        }
      });

      const responseText = response.choices[0]?.message?.content || "{}";
      res.json(JSON.parse(responseText));
    } catch (error: any) {
      console.error("Risk Analysis Error:", error);
      res.status(500).json({ error: error.message });
    }
  });

  // 3. Generate Executive Report Data (Report Agent)
  app.post("/api/generate-report-data", async (req, res) => {
    try {
      const { visionResults, riskResults, projectContext } = req.body;

      const prompt = `
        As an expert Construction Audit AI, generate a comprehensive executive summary based on these findings:
        Vision Analysis: ${JSON.stringify(visionResults)}
        Risk Analysis: ${JSON.stringify(riskResults)}
        Project Context: ${JSON.stringify(projectContext)}
      `;

      const response = await openai.chat.completions.create({
        model: "gemini-3.1-flash-lite",
        messages: [
          { role: "user", content: prompt }
        ],
        response_format: {
          type: "json_schema",
          json_schema: {
            name: "report_generation",
            strict: true,
            schema: {
              type: "object",
              properties: {
                executive_summary: { type: "string" },
                key_safety_takeaways: { type: "array", items: { type: "string" } },
                timeline_outlook: { type: "string" },
                budget_outlook: { type: "string" },
                critical_actions: { type: "array", items: { type: "string" } }
              },
              required: ["executive_summary", "key_safety_takeaways", "timeline_outlook", "budget_outlook", "critical_actions"],
              additionalProperties: false
            }
          }
        }
      });

      const responseText = response.choices[0]?.message?.content || "{}";
      res.json(JSON.parse(responseText));
    } catch (error: any) {
      console.error("Report Analysis Error:", error);
      res.status(500).json({ error: error.message });
    }
  });

  // 4. Analyze PDF Report (Unified Agent)
  app.post("/api/analyze-pdf-report", async (req, res) => {
    try {
      const { pdfText } = req.body;
      if (!pdfText) return res.status(400).json({ error: "No PDF text provided" });

      const prompt = `
        You are the ultimate Construction Site AI auditor. You have been given the full text content extracted from a project PDF document (daily report, audit, design document, or schedule).
        
        Analyze this text carefully and extract:
        1. All safety violations, safety hazards, or regulatory compliance issues mentioned or implied.
        2. Overall progress of the construction site.
        3. Overall safety score (0-100).
        4. Summary of the site status.
        5. Timeline risks, days behind schedule, cost overrun risk, top risk factors, and recommended actions.
        6. Determine a predicted 'target_end_date' (string, e.g. "Oct 24, 2026" or calculated based on schedule information).
        7. Determine a predicted 'risk_status' (string, e.g. "On Track", "Slight Delay", "Critical Delay", "High Risk").
        8. For 'top_risks', return an array of objects containing 'factor' (string), 'severity' ("HIGH" or "MEDIUM" or "LOW"), and 'probability' (number, 0-100).
        
        Document Text:
        ${pdfText}
      `;

      const response = await openai.chat.completions.create({
        model: "gemini-3.1-flash-lite",
        messages: [
          { role: "user", content: prompt }
        ],
        response_format: {
          type: "json_schema",
          json_schema: {
            name: "pdf_report_analysis",
            strict: true,
            schema: {
              type: "object",
              properties: {
                visionResults: {
                  type: "object",
                  properties: {
                    violations: {
                      type: "array",
                      items: {
                        type: "object",
                        properties: {
                          type: { type: "string" },
                          severity: { type: "string" },
                          location: { type: "string" },
                          recommendation: { type: "string" }
                        },
                        required: ["type", "severity", "location", "recommendation"],
                        additionalProperties: false
                      }
                    },
                    progress_estimate: { type: "number" },
                    overall_safety_score: { type: "number" },
                    summary: { type: "string" },
                    confidence: { type: "number" }
                  },
                  required: ["violations", "progress_estimate", "overall_safety_score", "summary", "confidence"],
                  additionalProperties: false
                },
                riskResults: {
                  type: "object",
                  properties: {
                    delay_probability: { type: "number" },
                    days_behind_schedule: { type: "number" },
                    cost_overrun_risk: { type: "number" },
                    target_end_date: { type: "string" },
                    risk_status: { type: "string" },
                    top_risks: {
                      type: "array",
                      items: {
                        type: "object",
                        properties: {
                          factor: { type: "string" },
                          severity: { type: "string" },
                          probability: { type: "number" }
                        },
                        required: ["factor", "severity", "probability"],
                        additionalProperties: false
                      }
                    },
                    recommended_actions: { type: "array", items: { type: "string" } }
                  },
                  required: [
                    "delay_probability",
                    "days_behind_schedule",
                    "cost_overrun_risk",
                    "target_end_date",
                    "risk_status",
                    "top_risks",
                    "recommended_actions"
                  ],
                  additionalProperties: false
                }
              },
              required: ["visionResults", "riskResults"],
              additionalProperties: false
            }
          }
        }
      });

      const responseText = response.choices[0]?.message?.content || "{}";
      res.json(JSON.parse(responseText));
    } catch (error: any) {
      console.error("PDF Report Analysis Error:", error);
      res.status(500).json({ error: error.message });
    }
  });

  // Vite middleware for development
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Server running on http://localhost:${PORT}`);
  });
}

startServer();
