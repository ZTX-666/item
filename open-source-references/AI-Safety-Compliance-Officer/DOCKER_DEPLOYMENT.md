# 🚀 Docker Deployment Guide

## 📋 Overview

This guide explains how to deploy the AI Safety Compliance Officer as **microservices** using Docker containers.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       Video Source                               │
│                    (Camera / RTSP / File)                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Detection Service Container                     │
│  • YOLOv11n Computer Vision                                     │
│  • Detects PPE violations                                        │
│  • Uploads images to S3                                          │
│  • Sends messages to SQS Queue                                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     AWS SQS Queue                                │
│              (violation-report-queue)                            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Agent Service Container                        │
│  • LangChain + GPT-4 AI Agent                                    │
│  • Generates OSHA reports                                        │
│  • Creates PDF documents                                         │
│  • Uploads reports to S3                                         │
│  • Sends email notifications                                     │
│  • Logs to database (RDS/PostgreSQL)                             │
└─────────────────────────────────────────────────────────────────┘
```

## 🐳 Microservices

### 1. Detection Service
- **Dockerfile:** `Dockerfile.detection`
- **Entry Point:** `detection_service.py`
- **Purpose:** Computer vision workload
- **Resources:** CPU-intensive
- **AWS Target:** EC2 (t3.medium) or ECS Fargate

### 2. Agent Service
- **Dockerfile:** `Dockerfile.agent`
- **Entry Point:** `agent_service.py`
- **Purpose:** AI report generation
- **Resources:** Network I/O intensive
- **AWS Target:** EC2 (t3.small) or Lambda

## 🛠️ Local Development Setup

### Prerequisites
- Docker Desktop installed
- Docker Compose installed
- AWS account (or LocalStack for testing)
- OpenAI API key

### Step 1: Create Environment File

Create `.env` file with your credentials:

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-your-openai-key

# AWS Configuration (use LocalStack for local testing)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
SQS_QUEUE_URL=http://localstack:4566/000000000000/violation-queue
S3_BUCKET_NAME=safety-violations

# Database (use SQLite for local, PostgreSQL for production)
DB_CONNECTION_STRING=sqlite:///violations.db

# Email Configuration
EMAIL_ENABLED=true
EMAIL_SENDER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
EMAIL_RECIPIENTS=manager@company.com

# Video Source
VIDEO_SOURCE=0  # 0 for webcam, or path to video file

# LangSmith (optional)
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=
```

### Step 2: Build Docker Images

```bash
# Build Detection Service
docker build -f Dockerfile.detection -t safety-detection:latest .

# Build Agent Service
docker build -f Dockerfile.agent -t safety-agent:latest .
```

### Step 3: Run with Docker Compose (Local Testing)

```bash
# Start all services (includes LocalStack for AWS mocking)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Step 4: Create SQS Queue and S3 Bucket (LocalStack)

```bash
# Install AWS CLI
pip install awscli-local

# Create SQS queue
awslocal sqs create-queue --queue-name violation-queue

# Create S3 bucket
awslocal s3 mb s3://safety-violations

# Verify
awslocal sqs list-queues
awslocal s3 ls
```

## ☁️ AWS Production Deployment

### Step 1: Create AWS Resources

#### 1.1 Create SQS Queue
```bash
aws sqs create-queue \
  --queue-name violation-report-queue \
  --region us-east-1
```

#### 1.2 Create S3 Bucket
```bash
aws s3 mb s3://your-company-safety-violations --region us-east-1
```

#### 1.3 Create RDS PostgreSQL Database
```bash
aws rds create-db-instance \
  --db-instance-identifier safety-compliance-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username admin \
  --master-user-password YourPassword123 \
  --allocated-storage 20
```

### Step 2: Push Docker Images to ECR

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Create ECR repositories
aws ecr create-repository --repository-name safety-detection
aws ecr create-repository --repository-name safety-agent

# Tag images
docker tag safety-detection:latest YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/safety-detection:latest
docker tag safety-agent:latest YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/safety-agent:latest

# Push images
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/safety-detection:latest
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/safety-agent:latest
```

### Step 3: Deploy to ECS/EC2

#### Option A: ECS Fargate (Recommended for Agent Service)

Create `task-definition.json` for each service and deploy via ECS console or CLI.

#### Option B: EC2 with Docker

```bash
# SSH into EC2 instance
ssh -i your-key.pem ec2-user@your-instance-ip

# Pull and run Detection Service
docker run -d \
  --name safety-detection \
  -e AWS_REGION=us-east-1 \
  -e SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/YOUR_ACCOUNT/violation-report-queue \
  -e S3_BUCKET_NAME=your-company-safety-violations \
  -e VIDEO_SOURCE=0 \
  YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/safety-detection:latest

# Pull and run Agent Service
docker run -d \
  --name safety-agent \
  -e AWS_REGION=us-east-1 \
  -e SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/YOUR_ACCOUNT/violation-report-queue \
  -e S3_BUCKET_NAME=your-company-safety-violations \
  -e OPENAI_API_KEY=your-key \
  -e EMAIL_ENABLED=true \
  YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/safety-agent:latest
```

## 🧪 Testing

### Test Detection Service
```bash
# Run detection service with test video
docker run -it \
  -v $(pwd)/test_video.mp4:/app/test_video.mp4 \
  -e VIDEO_SOURCE=/app/test_video.mp4 \
  safety-detection:latest
```

### Test Agent Service
```bash
# Send test message to queue
aws sqs send-message \
  --queue-url YOUR_QUEUE_URL \
  --message-body '{"class_name":"no_helmet","confidence":0.95}'

# Monitor agent service logs
docker logs -f safety-agent
```

## 📊 Monitoring

### View Container Logs
```bash
docker logs -f safety-detection
docker logs -f safety-agent
```

### CloudWatch Logs (Production)
- Enable CloudWatch logging in ECS task definitions
- View logs at: https://console.aws.amazon.com/cloudwatch

## 🔒 Security Best Practices

1. **Use IAM Roles** instead of hardcoded AWS credentials
2. **Encrypt S3 buckets** at rest
3. **Use VPC** for RDS database
4. **Enable CloudTrail** for audit logging
5. **Rotate OpenAI API keys** regularly

## 🚦 Health Checks

Both services include health check endpoints:
- Detection: Checks if OpenCV is working
- Agent: Checks if LangChain is working

## 📈 Scaling

### Detection Service
- Scale horizontally by adding more camera feeds
- Use multiple EC2 instances or ECS tasks

### Agent Service
- Auto-scales based on SQS queue depth
- Use ECS Service Auto Scaling or Lambda

## 🐛 Troubleshooting

### Issue: Cannot access webcam in Docker
**Solution:** Use `--device /dev/video0:/dev/video0` flag (Linux only)

### Issue: SQS connection timeout
**Solution:** Check security groups and VPC configuration

### Issue: S3 permission denied
**Solution:** Verify IAM role has `s3:PutObject` and `s3:GetObject` permissions

## 📚 Next Steps

1. ✅ Dockerization (Complete)
2. ⏭️ CI/CD Pipeline (GitHub Actions)
3. ⏭️ Terraform Infrastructure as Code
4. ⏭️ Monitoring Dashboard (Grafana/Prometheus)

---

**Ready for Next Step:** CI/CD Pipeline Setup with GitHub Actions
