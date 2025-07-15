import os
from openai import OpenAI
import time

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def main():
    # Create directory
    dir_path = os.path.join(os.getcwd(), "test_minimal.scientia")
    os.makedirs(dir_path, exist_ok=True)
    print(f"Created directory: {dir_path}")
    
    # Write initial log
    with open(os.path.join(dir_path, "test.log"), "w") as f:
        f.write("Starting test...\n")
    
    # Make a simple API call
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Write a one-sentence hypothesis about AI."}
        ],
        temperature=0.7,
    )
    
    # Write the response
    with open(os.path.join(dir_path, "test.log"), "a") as f:
        f.write(f"Response: {response.choices[0].message.content}\n")
    
    print("Test completed. Check test.log for results.")

if __name__ == "__main__":
    main()
