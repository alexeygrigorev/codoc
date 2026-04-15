# This is a sample script with block markers for testing

# @block=setup
from openai import OpenAI

client = OpenAI()
# @end

# Some code not in any block (ignored)
x = 42

# @block=make-request
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello"}],
)
# @end

# @block=print-result
print(response.choices[0].message.content)
# @end
