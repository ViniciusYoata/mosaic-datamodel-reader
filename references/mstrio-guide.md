# Reference Guide: MSTrio Python SDK (`mstrio-py`)

The `mstrio-py` library is the official Python SDK for integrating with the Strategy / MicroStrategy REST API.

---

## 1. Installation

```bash
pip install mstrio-py
```

---

## 2. Connecting to the Environment

### Via Username and Password
```python
from mstrio.connection import Connection

conn = Connection(
    base_url="https://your-environment/MicroStrategyLibrary/api",
    username="your_username",
    password="your_password",
    project_name="Project Name",
    login_mode=1  # 1 = Standard, 16 = LDAP
)
```

### Via Session Token Captured by `browser_auth.py`
```python
import json
from mstrio.connection import Connection

with open(".mstr_session.json", "r") as f:
    session = json.load(f)

conn = Connection(
    base_url=f"{session['base_url']}/api",
    identity_token=session["auth_token"],
    project_name="Project Name"
)
```

---

## 3. Core Operations with Data Models & Cubes

### List Projects
```python
from mstrio.project_objects import Project

projects = Project.get_projects(conn)
for p in projects:
    print(f"Project: {p.name} | ID: {p.id}")
```

### Inspect Cubes / Mosaic Models (`SuperCube`)
```python
from mstrio.project_objects import SuperCube

# Retrieve cube by ID
cube = SuperCube(conn, id="3A82F20B2CC849B0970B289C86D8C83C")

print("Cube Name:", cube.name)
print("Attributes:", [attr['name'] for attr in cube.attributes])
print("Metrics:", [mtr['name'] for mtr in cube.metrics])

# Convert to Pandas DataFrame (for rapid inspection of loaded data)
df = cube.to_dataframe()
print(df.head())
```

### Search Cubes by Name
```python
from mstrio.project_objects import SuperCube

cubes = SuperCube.find_cubes(conn, name="Sales")
for c in cubes:
    print(f"Cube: {c.name} | ID: {c.id}")
```

---

## 4. Closing the Connection

Always close the connection upon completing operations:
```python
conn.close()
```
