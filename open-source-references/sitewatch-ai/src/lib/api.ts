export async function analyzePhoto(image: string, prompt?: string) {
  const response = await fetch("/api/analyze-photo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image, prompt }),
  });
  if (!response.ok) throw new Error("Failed to analyze photo");
  return response.json();
}

export async function analyzeRisk(scheduleData: any, visionResults: any) {
  const response = await fetch("/api/analyze-risk", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scheduleData, visionResults }),
  });
  if (!response.ok) throw new Error("Failed to analyze risk");
  return response.json();
}

export async function generateReportData(visionResults: any, riskResults: any, projectContext: any) {
  const response = await fetch("/api/generate-report-data", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ visionResults, riskResults, projectContext }),
  });
  if (!response.ok) throw new Error("Failed to generate report data");
  return response.json();
}

export async function parsePDF(pdfBase64: string) {
  const response = await fetch("/api/parse-pdf", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pdfBase64 }),
  });
  if (!response.ok) throw new Error("Failed to parse PDF");
  return response.json();
}

export async function analyzePDFReport(pdfText: string) {
  const response = await fetch("/api/analyze-pdf-report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pdfText }),
  });
  if (!response.ok) throw new Error("Failed to analyze PDF report");
  return response.json();
}
