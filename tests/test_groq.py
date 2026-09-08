import os
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

try:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": "Say exactly this and nothing else: Aegon connection successful."
            }
        ],
        max_tokens=20
    )
    print(response.choices[0].message.content)

except Exception as e:
    print(f"Connection failed: {e}")