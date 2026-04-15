---
notebooks:
  - id: nb
    path: sample.ipynb
scripts:
  - id: sc
    path: sample.py
---

# Test Template

Here is some code:

@@code nb:hello

Some text between directives.

@@code nb:hello lines=1-3 strip-spaces=4

Here is the output:

@@code-output nb:hello limit-lines=2

And a script block:

@@code sc:block-one
