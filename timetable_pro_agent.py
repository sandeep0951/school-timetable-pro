
from google import genai

client = genai.Client()

def run_agent(prompt: str):
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    return response.text

if __name__ == "__main__":
    prompt = "Create a schedule based on 6 working days and 8 periods per day."
    print(run_agent(prompt))
