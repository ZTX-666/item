"""
Setup script for AI Safety Compliance Officer
Run this after installing requirements to configure the system
"""

import os
import shutil

def setup():
    print("="*80)
    print("AI Safety Compliance Officer - Setup")
    print("="*80)
    print()
    
    # Check if .env exists
    if not os.path.exists('.env'):
        print("📝 Creating .env file...")
        shutil.copy('.env.example', '.env')
        print("✅ .env file created!")
        print()
        print("⚠️  IMPORTANT: Edit .env file and add your:")
        print("   - OpenAI API Key")
        print("   - Email credentials")
        print()
    else:
        print("✅ .env file already exists")
    
    # Check if model exists
    model_path = "models/best.onnx"
    if not os.path.exists(model_path):
        print()
        print("⚠️  Model not found!")
        print(f"   Please copy your PPE detection model to: {model_path}")
        print("   You can copy from: ../YOLOv8 safety kit detection for construction site/YOLO-Weights/best.onnx")
        print()
        
        # Try to copy from parent directory
        parent_model = "../YOLOv8 safety kit detection for construction site/YOLO-Weights/best.onnx"
        if os.path.exists(parent_model):
            response = input("   Found model in parent directory. Copy it? (y/n): ")
            if response.lower() == 'y':
                os.makedirs('models', exist_ok=True)
                shutil.copy(parent_model, model_path)
                print("   ✅ Model copied successfully!")
    else:
        print("✅ Model found!")
    
    # Create directories
    print()
    print("📁 Creating directories...")
    os.makedirs('reports', exist_ok=True)
    os.makedirs('violations', exist_ok=True)
    os.makedirs('models', exist_ok=True)
    print("✅ Directories created!")
    
    print()
    print("="*80)
    print("Setup Complete!")
    print("="*80)
    print()
    print("Next steps:")
    print("1. Edit .env file with your API keys")
    print("2. Ensure model is in models/best.onnx")
    print("3. Run: python safety_monitor.py --source 0  (for webcam)")
    print()
    print("For help: python safety_monitor.py --help")
    print("="*80)

if __name__ == "__main__":
    setup()
