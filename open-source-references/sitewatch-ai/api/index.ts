import express from "express";
import { OpenAI } from "openai";
import { PDFParse } from "pdf-parse";
import dotenv from "dotenv";

dotenv.config();

const app = express();
app.use(express.json({ limit: "50mb" }));

const apiKey = process.env.AIMLAPI_KEY;
const openai = new OpenAI({
  apiKey: apiKey || "dummy-key",
  baseURL: "https://api.aimlapi.com/v1"
});

// 1. Health check
app.get("/api/health", (req, res) => {
  res.json({ status: "ok" });
});

// 2. Parse PDF
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

// 3. Analyze Photo
app.post("/api/analyze-photo", async (req, res) => {
  try {
    const { image, prompt } = req.body;
    if (!image) return res.status(400).json({ error: "No image provided" });

    const promptText = prompt || `
      You are the ultimate safety auditor and construction progress manager. Analyze this construction site image.
      Provide a highly detailed analysis containing:
      1. Violations: Array of objects with type, severity (High/Medium/Low), location, and recommendation.
      2. Progress Estimate: Number (percentage from 0 to 100 based on visible construction phase).
      3. Safety Score: Number (overall safety rating from 0 to 100).
      4. Summary: String describing overall safety and progress.
      5. Confidence: Number between 0 and 1.
    `;

    const base64Data = image.replace(/^data:image\/\w+;base64,/, "");

    const response = await openai.chat.completions.create({
      model: "gemini-3.1-flash-lite",
      messages: [
        {
          role: "user",
          content: [
            { type: "text", text: promptText },
            {
              type: "image_url",
              image_url: {
                url: `data:image/jpeg;base64,${base64Data}`
              }
            }
          ]
        }
      ],
      response_format: {
        type: "json_schema",
        json_schema: {
          name: "construction_analysis",
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
    console.error("Photo Analysis Error:", error);
    res.status(500).json({ error: error.message });
  }
});

// 4. Analyze Risk
app.post("/api/analyze-risk", async (req, res) => {
  try {
    const { scheduleData, visionResults } = req.body;
    const prompt = `
      You are the chief risk officer for a massive construction firm.
      Analyze this project schedule data and visual progress results:
      
      Schedule Data:
      ${typeof scheduleData === "object" ? JSON.stringify(scheduleData) : scheduleData}
      
      Visual Site Findings:
      ${JSON.stringify(visionResults)}
      
      Generate a comprehensive risk analysis including:
      1. Delay Probability (0-100 percentage).
      2. Days Behind Schedule (number).
      3. Cost Overrun Risk (0-100 percentage).
      4. A predicted 'target_end_date' (string, e.g. "Oct 24, 2026" or calculated based on timeline drift).
      5. A predicted 'risk_status' (string, e.g. "On Track", "Slight Delay", "Critical Delay", "High Risk").
      6. For 'top_risks', return an array of objects containing 'factor' (string), 'severity' ("HIGH" or "MEDIUM" or "LOW"), and 'probability' (number, 0-100).
      7. Recommended Actions (array of strings).
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

// 5. Generate Report Data
app.post("/api/generate-report-data", async (req, res) => {
  try {
    const { visionResults, riskResults, projectContext } = req.body;
    const prompt = `
      Create a compliance-ready construction site audit report based on these parameters:
      
      Visual Findings:
      ${JSON.stringify(visionResults)}
      
      Predictive Risk Analysis:
      ${JSON.stringify(riskResults)}
      
      Project Context:
      ${typeof projectContext === "object" ? JSON.stringify(projectContext) : projectContext}
      
      Return a structured JSON containing:
      1. Executive Summary: string.
      2. Key Safety Takeaways: array of strings.
      3. Timeline Outlook: string.
      4. Budget Outlook: string.
      5. Critical Actions: array of strings.
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

// 6. Analyze PDF Report (Unified Agent)
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

export default app;
