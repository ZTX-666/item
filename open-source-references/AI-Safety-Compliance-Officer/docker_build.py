"""
Docker Build and Test Script
Purpose: Automate building and testing of Docker containers locally
"""

import subprocess
import sys
import os

def run_command(command, description):
    """Run a shell command and handle errors"""
    print(f"\n{'='*80}")
    print(f"🔨 {description}")
    print(f"{'='*80}")
    print(f"Command: {command}\n")
    
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✅ {description} - SUCCESS")
        if result.stdout:
            print(result.stdout)
    else:
        print(f"❌ {description} - FAILED")
        if result.stderr:
            print(result.stderr)
        return False
    
    return True

def check_docker():
    """Check if Docker is installed and running"""
    print("Checking Docker installation...")
    if not run_command("docker --version", "Docker Version Check"):
        print("❌ Docker is not installed. Please install Docker Desktop.")
        return False
    
    if not run_command("docker ps", "Docker Daemon Check"):
        print("❌ Docker daemon is not running. Please start Docker Desktop.")
        return False
    
    return True

def check_env_file():
    """Check if .env file exists"""
    if not os.path.exists(".env"):
        print("⚠️  Warning: .env file not found!")
        print("Creating .env from .env.example...")
        
        if os.path.exists(".env.example"):
            subprocess.run("copy .env.example .env", shell=True)
            print("✅ Created .env file. Please edit it with your credentials.")
        else:
            print("❌ .env.example not found. Please create .env manually.")
        
        return False
    return True

def build_images():
    """Build Docker images"""
    print("\n" + "="*80)
    print("🏗️  BUILDING DOCKER IMAGES")
    print("="*80)
    
    # Build Detection Service
    if not run_command(
        "docker build -f Dockerfile.detection -t safety-detection:latest .",
        "Building Detection Service Image"
    ):
        return False
    
    # Build Agent Service
    if not run_command(
        "docker build -f Dockerfile.agent -t safety-agent:latest .",
        "Building Agent Service Image"
    ):
        return False
    
    return True

def list_images():
    """List built images"""
    run_command(
        "docker images | findstr safety",
        "Listing Safety Service Images"
    )

def test_detection_service():
    """Test Detection Service container"""
    print("\n" + "="*80)
    print("🧪 TESTING DETECTION SERVICE")
    print("="*80)
    
    run_command(
        "docker run --rm safety-detection:latest python -c \"import cv2; import ultralytics; print('Detection service dependencies OK')\"",
        "Testing Detection Service Dependencies"
    )

def test_agent_service():
    """Test Agent Service container"""
    print("\n" + "="*80)
    print("🧪 TESTING AGENT SERVICE")
    print("="*80)
    
    run_command(
        "docker run --rm safety-agent:latest python -c \"import langchain; import reportlab; print('Agent service dependencies OK')\"",
        "Testing Agent Service Dependencies"
    )

def show_summary():
    """Show deployment summary"""
    print("\n" + "="*80)
    print("📋 DEPLOYMENT SUMMARY")
    print("="*80)
    print("""
✅ Docker images built successfully!

Next Steps:
1. Edit .env file with your credentials (OpenAI, AWS, Email)
2. Test locally with LocalStack:
   docker-compose up -d

3. For AWS deployment:
   - Create SQS queue
   - Create S3 bucket
   - Push images to ECR
   - Deploy to ECS/EC2

See DOCKER_DEPLOYMENT.md for detailed instructions.
""")

def main():
    """Main execution"""
    print("="*80)
    print("🐳 AI Safety Compliance Officer - Docker Build Script")
    print("="*80)
    
    # Step 1: Check prerequisites
    if not check_docker():
        sys.exit(1)
    
    # Step 2: Check environment file
    check_env_file()
    
    # Step 3: Build images
    if not build_images():
        print("\n❌ Build failed. Please check error messages above.")
        sys.exit(1)
    
    # Step 4: List images
    list_images()
    
    # Step 5: Test images
    test_detection_service()
    test_agent_service()
    
    # Step 6: Show summary
    show_summary()
    
    print("="*80)
    print("✅ Docker setup complete!")
    print("="*80)

if __name__ == "__main__":
    main()
