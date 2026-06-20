# 📊 LangSmith Monitoring Guide

## What is LangSmith?

LangSmith is LangChain's observability platform that helps you:
- **Debug** AI agent interactions
- **Monitor** performance and costs
- **Trace** LLM calls with full context
- **Analyze** token usage and latency
- **Improve** prompts based on real data

## 🎯 What Gets Monitored

### In Your AI Safety Compliance Officer:

1. **Every AI Report Generation**
   - Full prompt sent to GPT-4
   - AI response (OSHA report)
   - Token usage (input + output)
   - Latency/response time
   - Cost per request

2. **Violation Context**
   - Violation type (no_helmet, no_vest, etc.)
   - Confidence score
   - OSHA regulation violated
   - Site location
   - Timestamp

3. **Performance Metrics**
   - Average tokens per report
   - Total reports generated
   - Success/failure rates
   - Response times

## 🚀 Setup Instructions

### Step 1: Get LangSmith API Key

1. Go to: https://smith.langchain.com
2. Sign up for free account (no credit card required)
3. Click on **Settings** (gear icon)
4. Click **API Keys** → **Create API Key**
5. Copy your API key

### Step 2: Configure Environment

Edit your `.env` file:

```env
# Enable LangSmith Monitoring
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=ai-safety-compliance-officer
```

### Step 3: Install/Update Dependencies

```powershell
pip install langsmith
# Or reinstall all requirements
pip install -r requirements.txt
```

### Step 4: Run Your System

```powershell
python safety_monitor.py --source 0
```

You'll see:
```
✅ LangSmith monitoring enabled
```

## 📈 What You'll See in LangSmith

### 1. Dashboard
- **Total runs** (number of AI reports generated)
- **Token usage** (cost tracking)
- **Latency** (response times)
- **Success rate**

### 2. Individual Traces
Click any trace to see:
- **Input Prompt**: Full prompt sent to GPT-4
- **Output**: Generated OSHA report
- **Metadata**: Violation type, confidence, site, timestamp
- **Performance**: Token count, cost, duration
- **Tags**: `safety-report`, `osha-compliance`, violation type

### 3. Project View
All your safety reports organized by:
- Date/time
- Violation type
- Success/failure
- Performance metrics

## 🔍 Example Trace

When a violation is detected, LangSmith records:

```
Trace: Safety Incident Report Generation
├─ Input Variables:
│  ├─ violation_type: "No Helmet"
│  ├─ confidence: 94.5%
│  ├─ date: November 29, 2025
│  ├─ location: Zone 3, Building B
│  └─ osha_regulation: 29 CFR 1926.100(a)
│
├─ LLM Call (gpt-4):
│  ├─ Prompt: [Full prompt with all variables]
│  ├─ Response: [Generated OSHA report]
│  ├─ Tokens: 450 input + 850 output = 1,300 total
│  ├─ Cost: $0.052
│  └─ Duration: 3.2 seconds
│
├─ Metadata:
│  ├─ site: Construction Site A
│  ├─ application: AI Safety Compliance Officer
│  └─ version: 1.0
│
└─ Tags: [safety-report, osha-compliance, no_helmet]
```

## 📊 Viewing Statistics

### In Your Application
Press **'s'** during monitoring to see:

```
🤖 AI Agent Usage:
   - Reports generated: 15
   - Total tokens used: 19,500
   - Avg tokens/report: 1,300
   - LangSmith monitoring: ✅ Enabled
   - View traces at: https://smith.langchain.com
```

### In LangSmith Dashboard

1. Go to https://smith.langchain.com
2. Select project: **ai-safety-compliance-officer**
3. View:
   - Timeline of all reports
   - Token usage trends
   - Cost analysis
   - Performance metrics

## 💡 Use Cases

### 1. Debugging Prompts
**Problem**: AI reports not detailed enough

**Solution**:
- View actual prompts in LangSmith
- See what GPT-4 received
- Adjust prompt template in `compliance_agent.py`
- Compare before/after results

### 2. Cost Optimization
**Problem**: High OpenAI costs

**Solution**:
- Check average tokens per report
- Identify if prompts are too long
- Consider using GPT-3.5-turbo for simpler reports
- Track cost trends over time

### 3. Performance Analysis
**Problem**: Slow report generation

**Solution**:
- View latency for each request
- Identify slow responses
- Optimize prompt length
- Consider caching common responses

### 4. Quality Assurance
**Problem**: Some reports have issues

**Solution**:
- Filter by violation type
- Compare successful vs failed reports
- Identify patterns in good/bad outputs
- Refine prompts based on data

## 🔧 Configuration Options

### Change Project Name
```env
LANGCHAIN_PROJECT=my-construction-site-A
```
Creates separate project in LangSmith

### Disable Monitoring Temporarily
```env
LANGCHAIN_TRACING_V2=false
```
Monitoring disabled (useful for testing)

### Custom Metadata
Edit `compliance_agent.py` to add more metadata:

```python
config={
    "metadata": {
        "custom_field": "your_value",
        "inspector": "John Doe",
        "zone": "high_risk_area"
    }
}
```

## 📈 Advanced Features

### 1. Datasets
- Save good reports as examples
- Test prompt changes against dataset
- Ensure quality consistency

### 2. Feedback
- Rate report quality (thumbs up/down)
- Add comments to specific reports
- Track improvement over time

### 3. Comparison
- Compare different prompts
- A/B test GPT-4 vs GPT-3.5
- Measure quality vs cost

### 4. Alerts
- Get notified of failures
- Monitor token usage spikes
- Track latency issues

## 💰 Pricing

LangSmith has a **free tier**:
- ✅ Unlimited traces
- ✅ 14 days retention
- ✅ Full features

Paid plans (if needed):
- Extended retention
- Team collaboration
- Advanced analytics

## 🎯 Best Practices

### 1. Use Descriptive Tags
```python
tags=["safety-report", "construction-site-A", "critical"]
```

### 2. Add Rich Metadata
Include all relevant context:
- Violation details
- Site information
- Weather conditions
- Time of day

### 3. Review Regularly
- Check dashboard weekly
- Identify trends
- Optimize based on data

### 4. Test Before Production
- Test prompts in LangSmith
- Compare outputs
- Roll out best version

## 🔗 Useful Links

- **LangSmith Dashboard**: https://smith.langchain.com
- **Documentation**: https://docs.smith.langchain.com
- **API Reference**: https://api.python.langchain.com/en/latest/smith/langsmith.html
- **Examples**: https://github.com/langchain-ai/langsmith-cookbook

## 🆘 Troubleshooting

### "LangSmith monitoring disabled"
**Solution**: Check `.env` file has:
```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_key_here
```

### Not seeing traces in dashboard
**Solution**:
1. Check API key is correct
2. Ensure internet connection
3. Wait ~30 seconds for traces to appear
4. Verify project name matches

### High token usage
**Solution**:
1. View prompts in LangSmith
2. Check if prompt is too long
3. Remove unnecessary context
4. Consider shorter violation descriptions

## 📊 Example Dashboard Insights

After running for a week, you might see:

```
📈 Weekly Report (Nov 22-29, 2025)

Total Violations Detected: 47
Reports Generated: 47
Success Rate: 100%

Token Usage:
├─ Total: 61,100 tokens
├─ Average: 1,300 tokens/report
├─ Input: 21,150 tokens (35%)
└─ Output: 39,950 tokens (65%)

Cost Analysis:
├─ Total: $2.44
├─ Average: $0.052/report
└─ Projected Monthly: $10.50

Performance:
├─ Avg Latency: 3.2 seconds
├─ Fastest: 2.1 seconds
└─ Slowest: 5.8 seconds

Top Violations:
├─ no_helmet: 22 (47%)
├─ no_vest: 15 (32%)
└─ no_gloves: 10 (21%)
```

## ✨ Benefits

1. **Transparency**: See exactly what AI generates
2. **Debugging**: Quickly identify issues
3. **Optimization**: Reduce costs and improve speed
4. **Quality**: Ensure consistent report quality
5. **Compliance**: Audit trail of all AI decisions

## 🎉 Summary

**LangSmith gives you full visibility into your AI agent:**
- ✅ Every prompt and response logged
- ✅ Token usage and costs tracked
- ✅ Performance metrics monitored
- ✅ Easy debugging and optimization
- ✅ Professional audit trail

**Enable it in 3 steps:**
1. Get API key from smith.langchain.com
2. Add to `.env` file
3. Run your system!

---

**Your AI Safety Compliance Officer is now monitored! 🎉**

View all traces at: https://smith.langchain.com
