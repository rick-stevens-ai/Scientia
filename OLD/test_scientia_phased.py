import os
import json
import time
from datetime import datetime
from openai import OpenAI

def create_project_directory(base_name):
    base_dir = os.path.join(os.getcwd(), f"{base_name}.scientia")
    if os.path.exists(base_dir):
        version = 1
        while os.path.exists(f"{base_dir}.{version}"):
            version += 1
        base_dir = f"{base_dir}.{version}"
    os.makedirs(base_dir)
    print(f"Created directory: {base_dir}")
    return base_dir

def write_progress(dir_path, phase, content):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Write to progress log
    with open(os.path.join(dir_path, "progress.log"), "a") as f:
        f.write(f"\n===== {phase} - {timestamp} =====\n")
        f.write(content + "\n")
    
    # Write to phase-specific file
    phase_file = os.path.join(dir_path, f"{phase}.json")
    with open(phase_file, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "content": content
        }, f, indent=2)
    
    print(f"Completed phase: {phase}")

def main():
    # Create project directory
    project_dir = create_project_directory("ai_test")
    
    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Phase 1: Generate initial idea
        print("Starting Phase 1: Initial Generation")
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a scientific hypothesis generator."},
                {"role": "user", "content": "Generate one hypothesis about AI and quantum computing."}
            ],
            temperature=0.7,
        )
        write_progress(project_dir, "phase1_generation", response.choices[0].message.content)
        
        time.sleep(2)  # Brief pause between API calls
        
        # Phase 2: Analyze hypothesis
        print("Starting Phase 2: Analysis")
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a scientific hypothesis analyzer."},
                {"role": "user", "content": "Analyze this hypothesis for plausibility and novelty."},
                {"role": "assistant", "content": response.choices[0].message.content}
            ],
            temperature=0.7,
        )
        write_progress(project_dir, "phase2_analysis", response.choices[0].message.content)
        
        # Write completion status
        with open(os.path.join(project_dir, "status.txt"), "w") as f:
            f.write("Completed successfully")
        
        print(f"\nProcess completed. Results saved in: {project_dir}")
        
    except Exception as e:
        error_msg = f"Error during execution: {str(e)}"
        print(error_msg)
        with open(os.path.join(project_dir, "error.log"), "w") as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {error_msg}")
        raise

if __name__ == "__main__":
    main()
