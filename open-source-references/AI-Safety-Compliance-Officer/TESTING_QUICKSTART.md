# 🚀 TESTING QUICKSTART

## 📌 Three Ways to Test Your System

### 🎯 Option 1: Interactive Menu (RECOMMENDED)
```powershell
python test_menu.py
```
**Benefits:**
- Easy-to-use menu interface
- Run individual tests
- Check system status
- Perfect for beginners

---

### 🤖 Option 2: Automated Test Suite
```powershell
python run_all_tests.py
```
**Benefits:**
- Runs all tests automatically
- Generates comprehensive report
- Good for CI/CD preparation
- Takes 5-10 minutes

---

### 🔧 Option 3: Manual Testing

#### Test 1: Database ✅
```powershell
python test_database.py
```

#### Test 2: Computer Vision 👁️
```powershell
python test_detector.py
```
*Stand in front of webcam - test detections*

#### Test 3: AI Agent 🤖
```powershell
python test_agent.py
```
*Requires: OPENAI_API_KEY in .env*

#### Test 4: PDF Reports 📄
```powershell
python test_pdf.py
```

#### Test 5: Email Alerts 📧
```powershell
python test_email_simple.py
```
*Requires: Email config in .env*

#### Test 6: Full System 🎯
```powershell
python test_full_system.py
```
*30-second live test of entire pipeline*

#### Test 7: Dashboard 🎛️
Already running at: http://localhost:5000

---

## ⚡ Quick 5-Minute Test

Want to test everything quickly? Run these 3 commands:

```powershell
# 1. Test core components (1 min)
python test_database.py

# 2. Test detection (30 sec)
python test_detector.py

# 3. Check dashboard (open browser)
# Already running: http://localhost:5000
```

✅ If these pass, your system works!

---

## 🛠️ Prerequisites Check

Before testing, verify:

```powershell
# Check Python version
python --version  # Should be 3.11+

# Check packages installed
pip list | Select-String "ultralytics|langchain|flask"

# Check model exists
Test-Path ".\models\best.onnx"

# Check .env file
Get-Content .env
```

---

## 📝 Test Results Checklist

After testing, you should have:

✅ **Database**: violations.db created and working  
✅ **Detection**: Webcam detections working  
✅ **AI Reports**: GPT-4 generating reports (if API key set)  
✅ **PDF Files**: Reports in reports/ folder  
✅ **Email**: Test email received (if configured)  
✅ **Dashboard**: Web interface at localhost:5000  

---

## 🐛 Common Issues

### Issue: "Model file not found"
**Solution**: You need to train or download YOLOv8 model
```powershell
# Place model in: models/best.onnx
```

### Issue: "OPENAI_API_KEY not found"
**Solution**: Add to .env file
```
OPENAI_API_KEY=sk-your-key-here
```

### Issue: "Cannot open webcam"
**Solution**: Close other apps using camera, or try different index
```python
# In test, change: video_source=1 or video_source=2
```

### Issue: "Email authentication failed"
**Solution**: Use Gmail App Password (not regular password)
- Enable 2FA on Gmail
- Generate App Password
- Use that in EMAIL_PASSWORD

---

## 📊 What Each Test Does

| Test | Duration | What it checks |
|------|----------|----------------|
| Database | 10 sec | SQLite operations, CRUD |
| Detector | 10 sec | YOLOv8 model, webcam access |
| AI Agent | 10 sec | GPT-4 API, report generation |
| PDF | 10 sec | ReportLab, file creation |
| Email | 10 sec | SMTP, Gmail connectivity |
| Full System | 30 sec | Complete pipeline end-to-end |
| Dashboard | Manual | Web UI, REST API |

**Total time**: ~5-10 minutes for all tests

---

## 🎯 Next Steps After Testing

### All Tests Pass ✅
1. Document your test results
2. Review generated reports
3. Proceed to **CI/CD setup** or **AWS deployment**

### Some Tests Fail ❌
1. Check error messages
2. Review prerequisites
3. See troubleshooting in LOCAL_TESTING_GUIDE.md
4. Fix issues and re-test

### Optional Tests Skipped ⚠️
That's OK! These require additional setup:
- **AI Agent**: Needs OpenAI API key ($)
- **Email**: Needs Gmail app password

You can skip them for now and still deploy.

---

## 💡 Pro Tips

1. **Start with test_menu.py** - It's the easiest way
2. **Test detector with real PPE** - Wear/remove helmet to trigger
3. **Check dashboard while testing** - See real-time updates
4. **Save test results** - Screenshot or copy output
5. **Run full system last** - After individual tests pass

---

## 📞 Need Help?

If tests fail:
1. Check error messages carefully
2. Review LOCAL_TESTING_GUIDE.md (detailed guide)
3. Check .env configuration
4. Verify all packages installed
5. Share error output for debugging

---

## 🚀 Ready for Production?

Once all tests pass:
- ✅ System validated locally
- ✅ Ready for CI/CD
- ✅ Ready for Docker
- ✅ Ready for AWS deployment

**Next command:**
```powershell
# Stop the tests and tell me you're ready for the next phase!
# I'll guide you through CI/CD setup or AWS deployment
```

---

Good luck with testing! 🧪✨
