# Codoc

Generate markdown documents from `.template.md` files backed by Jupyter notebooks and scripts.

Codoc extracts referenced cells and blocks, inserts them into markdown templates, and can validate notebook content by executing the source notebooks first.

## Installation

Install from PyPI:

```bash
pip install codoc
```

For development:

```bash
git clone git@github.com:alexeygrigorev/codoc.git
cd codoc
uv sync --dev
```

The main commands are `codoc`, `codoc-watch`, and `nbedit`.

## Usage

### Generate a single template

```bash
uv run python -m codoc path/to/file.template.md
```

This creates `path/to/file.md` (removing `.template` from the filename).

### Generate all templates in a directory

```bash
uv run python -m codoc path/to/folder
```

Recursively finds all `*.template.md` files and generates corresponding `.md` files.

### Options

- `--timeout SECONDS` - Timeout for each cell during validation (default: 30)
- `--kernel NAME` - Jupyter kernel name to use (default: python3)
- `-o, --output PATH` - Output file path (single file only)
- `-v, --verbose` - Enable verbose output

```bash
uv run python -m codoc templates/ --timeout 60 -v
```

### Watch mode

Watch for template file changes and automatically regenerate on edit:

```bash
uv run codoc-watch [path]
```

The watcher waits for a grace period (default 1.5s) after the last edit before triggering, so it doesn't run while you're actively typing.

Options:
- `-g, --grace-period SECONDS` - Wait time after last change (default: 1.5)
- `--timeout SECONDS` - Timeout for each cell during validation (default: 30)
- `--kernel NAME` - Jupyter kernel name to use (default: python3)
- `-v, --verbose` - Enable verbose output

```bash
# Watch current directory
uv run codoc-watch

# Watch specific path
uv run codoc-watch 01-foundation/02-rag/

# Verbose mode with longer grace period
uv run codoc-watch -v -g 2.0
```

## Notebook Editor

The notebook editor provides convenient CLI commands for manipulating Jupyter notebooks without editing JSON directly.

### Common Mistakes

**Wrong:** Using `--` after cell_id (confusing with other CLI conventions)

```bash
cat << 'EOF' | nbedit nb.ipynb update my-cell --
code here
EOF
```

**Correct:** Use `--code -` for stdin

```bash
cat << 'EOF' | nbedit nb.ipynb update my-cell --code -
code here
EOF
```

The `--` separator used by some tools (like git) is NOT valid in nbedit. Always use `--code` followed by the code content or `-` for stdin.

### Indexing Note

Cell indices use **1-based indexing** (1, 2, 3...) instead of 0-based. This matches how humans count and is more intuitive when working with line numbers in editors. If you're used to 0-based indexing from programming, just add 1 when referring to cell positions.

### Batch Mode (Recommended)

For most workflows, use batch mode to execute multiple commands at once. Show comprehensive batch mode help:

```bash
uv run nbedit --batch-help
```

Create a batch file with commands starting with `@>>`:

```bash
uv run nbedit notebook.ipynb --batch batch-file.txt
```

Use `-` for stdin:

```bash
cat batch.txt | uv run nbedit notebook.ipynb --batch -
```

The notebook is automatically created if it doesn't exist, and saved after all commands complete.

#### Comments

Lines starting with `-- ` (double dash followed by a space) are treated as comments and ignored.

```
-- This is a comment
-- So is this

@>> add --id my-cell
print("hello")
```

#### Batch Commands

- `add [--id ID]` - Add a code cell with optional @cell_id
- `add --markdown` - Add a markdown cell
- `insert-after INDEX|ID [--id ID]` - Insert after index or cell_id
- `update INDEX|ID` - Update cell by index or ID
- `delete INDEX|ID` - Delete cell by index or ID
- `rename ID --new-id NEW` - Rename a cell ID
- `add-id INDEX ID` - Add @cell_id to cell at index
- `move ID AFTER_ID` - Move cell after another cell

#### Batch Examples

**Creating a new notebook:**

```
@>> add --id setting-up
from openai import OpenAI
client = OpenAI()

@>> add --id first-request
messages = [{"role": "user", "content": "hello"}]
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages
)
print(response.choices[0].message.content)
```

**Updating an existing cell by ID:**

```
@>> update my-cell --code
def new_function():
    return "updated"
```

**Deleting a cell by index (1-based):**

```
@>> delete 3
```

**Renaming a cell ID:**

```
@>> rename old-id --new-id new-id
```

**Moving a cell after another:**

```
@>> move cell-to-move target-cell
```

#### Common Scenarios

**Create a notebook from scratch:**

```
@>> add --id imports
import pandas as pd
import numpy as np

@>> add --id load-data
df = pd.read_csv("data.csv")
print(df.head())

@>> add --id process
df["total"] = df["quantity"] * df["price"]
print(df.describe())
```

**Add a cell after an existing one:**

```
@>> insert-after load-data --id visualize
import matplotlib.pyplot as plt
df.plot(x="date", y="total")
plt.show()
```

### Single Command Mode

For quick operations, use single commands. The notebook is auto-created if it doesn't exist.

List cells (to check state before editing):

```bash
uv run nbedit notebook.ipynb list
uv run nbedit notebook.ipynb list --with-output --limit 20
uv run nbedit notebook.ipynb list --line-numbers
```

The `--line-numbers` (or `-n`) flag shows 1-based line numbers for code cells. Use this to identify line ranges for the `lines=` parameter in `@@code` directives.

Add a code cell with an optional `@cell_id` marker:

```bash
uv run nbedit notebook.ipynb add --code "print('hello')" --id my-cell
```

Add a markdown cell:

```bash
uv run nbedit notebook.ipynb add --markdown "# Heading"
```

Read code from stdin:

```bash
echo "print('hello')" | uv run nbedit notebook.ipynb add --code -
```

Insert after a cell by ID:

```bash
uv run nbedit notebook.ipynb insert-after existing-id --code "new code" --id new-id
```

Update by cell ID:

```bash
uv run nbedit notebook.ipynb update cell-id --code "updated code"
```

Delete by index or ID:

```bash
uv run nbedit notebook.ipynb delete 3
uv run nbedit notebook.ipynb delete cell-id
```

Rename cell ID:

```bash
uv run nbedit notebook.ipynb rename old-id --new-id new-id
```

Add @cell_id marker to existing cell (1-based index):

```bash
uv run nbedit notebook.ipynb add-id 3 my-new-id
```

Move cell after another:

```bash
uv run nbedit notebook.ipynb move cell-id after-id
```

Remove all @cell_id markers:

```bash
uv run nbedit notebook.ipynb remove-ids
```

## Template Syntax

### Frontmatter

Define notebook and script references in YAML frontmatter:

```yaml
---
notebooks:
  - id: openai-basics
    path: ../../notebooks/02-openai-api.ipynb
    execute: true
  - id: doc-agent
    path: ../../notebooks/03-documentation-agent.ipynb
    execute: false
scripts:
  - id: test
    path: test_agent.py
---
```

Notebook fields:
- `id` - Identifier for this notebook (used in directives)
- `path` - Path to the notebook file (relative to template file)
- `execute` - Whether to execute the notebook during generation (default: `true`)

Script fields:
- `id` - Identifier for this script (used in directives)
- `path` - Path to the script file (relative to template file)

Set `execute: false` for notebooks that:
- Make external API calls
- Have long execution times
- Access resources not available during generation

IDs must be unique across both notebooks and scripts in the same template.

### Directives

Use `@@code` to include cell source code (from notebooks) or block source code (from scripts):

```markdown
@@code openai-basics:create-client
@@code test:setup
```

Use `@@code-output` to include cell output (notebooks only):

```markdown
@@code-output openai-basics:create-client
```

`@@code-output` and `@@code-figure` are not supported for scripts (scripts have no execution output).

To limit the number of output lines (useful for long outputs):

```markdown
@@code-output openai-basics:create-client limit-lines=5
```

This shows only the first 5 lines, followed by `...` if the output exceeds the limit.

You can also limit by character count:

```markdown
@@code-output openai-basics:create-client limit-chars=100
```

This shows only the first 100 characters, followed by `...` if the output exceeds the limit.

Both limits can be used together (lines are applied first, then characters):

```markdown
@@code-output openai-basics:create-client limit-lines=5 limit-chars=100
```

To extract specific lines from a cell (useful for showing a method from a class):

```markdown
@@code openai-basics:my-class lines=2-4
```

This extracts only lines 2 through 4 (1-based, inclusive). Use `lines=3` for a single line.

To remove leading spaces from each line (useful for dedenting class methods):

```markdown
@@code openai-basics:my-class lines=2-4 strip-spaces=4
```

This removes up to 4 leading spaces from each extracted line. Empty lines are unaffected.

The workflow: run `nbedit notebook.ipynb list --line-numbers` to see numbered code, then use `lines=` and `strip-spaces=` in your template.

### Notebook Cells

Mark cells in Jupyter notebooks with `# @cell_id=`:

```python
# @cell_id=create-client
from openai import OpenAI
client = OpenAI()
```

### Script Blocks

Mark blocks in script files with `# @block=name` and `# @end`:

```python
# @block=setup
from openai import OpenAI
client = OpenAI()
# @end

# code outside blocks is ignored

# @block=make-request
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "hello"}]
)
# @end
```

The code fence language is automatically set to `python` for `.py` files.

## Example

**Template (`02-openai-api.template.md`):**

```markdown
---
notebooks:
  - id: openai-basics
    path: ../../notebooks/02-openai-api.ipynb
    execute: true
---

# Using the OpenAI API

Let's start by creating a client.

@@code openai-basics:create-client

Now we can make a request:

@@code openai-basics:make-request

The response looks like this:

@@code-output openai-basics:make-request
```

**Notebook (`02-openai-api.ipynb`) cell:**

```python
# @cell_id=create-client
from openai import OpenAI
client = OpenAI()
```

**Generated (`02-openai-api.md`):**

```markdown
# Using the OpenAI API

Let's start by creating a client.

```python
from openai import OpenAI
client = OpenAI()
```

Now we can make a request:

```python
messages = [{"role": "user", "content": "tell me a joke"}]
response = client.chat.completions.create(...)
```

The response looks like this:

```python
ChatCompletionMessage(content="Why did the chicken...", role='assistant')
```
```

## Script Example

**Template (`02-testing.template.md`):**

```markdown
---
scripts:
  - id: test
    path: test_agent.py
---

# Testing the Agent

Set up the test fixtures:

@@code test:setup

Run the actual test:

@@code test:test-function
```

**Script (`test_agent.py`):**

```python
# @block=setup
import pytest
from agent import Agent
# @end

# @block=test-function
def test_agent_responds():
    agent = Agent()
    result = agent.run("hello")
    assert "hello" in result.lower()
# @end
```

**Generated (`02-testing.md`):**

```markdown
# Testing the Agent

Set up the test fixtures:

```python
import pytest
from agent import Agent
```

Run the actual test:

```python
def test_agent_responds():
    agent = Agent()
    result = agent.run("hello")
    assert "hello" in result.lower()
```
```

## Development

### Run tests

```bash
uv run pytest
```

### Create test fixtures

```bash
uv run python tests/create_fixtures.py
```

This creates the test notebook fixtures in `tests/fixtures/notebooks/` by executing them and saving with outputs.
