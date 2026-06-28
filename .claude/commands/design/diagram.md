---
description: Generate architecture diagrams for a component or system — selects the right Mermaid diagram type for the context
argument-hint: [component or system to diagram]
allowed-tools: Read, Write, Grep, Glob
---

Generate architecture diagrams for: $ARGUMENTS

# Architecture Diagramming — Rigorous Mermaid Output

This command produces the right diagram(s) for the context. Do not default to a sequence
diagram for everything — choose diagram types that reveal structure, not just flow.

---

## Step 1: Identify what you need to show

| Question | Best diagram type |
|----------|------------------|
| Where does this system sit among external actors? | **C4 Context** |
| What are the major containers/services inside the system? | **C4 Container** |
| What are the components inside a single container? | **C4 Component** |
| How do objects/services call each other over time? | **Sequence** |
| What states can an entity move through? | **State** |
| What are the data entities and their relationships? | **Entity-Relationship (ERD)** |
| How does the system deploy — hosts, networks, zones? | **Deployment** |
| What are the task or build dependencies? | **Directed Graph (flowchart)** |
| How does a class hierarchy or interface relate? | **Class** |

Produce **only the diagrams that add information**. If a sequence diagram and a flowchart would
show the same thing, produce the sequence diagram — it shows order, which a flowchart does not.

---

## Diagram Type Reference

### C4 Context Diagram
Shows the system in relation to external users and systems. One diagram per system.

```mermaid
C4Context
    title System Context — [System Name]
    Person(user, "Primary User", "Description of what they do")
    System(sys, "[System Name]", "What it does in one line")
    System_Ext(ext1, "External System A", "What it provides")
    System_Ext(ext2, "External System B", "What it provides")

    Rel(user, sys, "Uses", "HTTPS")
    Rel(sys, ext1, "Reads from", "REST API")
    Rel(sys, ext2, "Writes to", "Event stream")
```

When to include:
- Always for the system-level architecture document
- In feature plan.md when the feature introduces a new external integration

---

### C4 Container Diagram
Shows the major deployable units (applications, databases, queues) inside the system boundary.

```mermaid
C4Container
    title Container Diagram — [System Name]
    Person(user, "User", "Description")

    System_Boundary(sys, "[System Name]") {
        Container(web, "Web App", "Python/FastAPI", "Serves HTTP requests")
        Container(worker, "Worker", "Python", "Processes background jobs")
        ContainerDb(db, "Database", "PostgreSQL", "Persists application state")
        Container(queue, "Queue", "Redis", "Job queue")
    }

    System_Ext(ext, "External API", "Third-party data source")

    Rel(user, web, "Uses", "HTTPS")
    Rel(web, queue, "Enqueues jobs", "Redis protocol")
    Rel(worker, queue, "Dequeues", "Redis protocol")
    Rel(worker, db, "Reads/writes", "SQL")
    Rel(worker, ext, "Calls", "REST HTTPS")
```

When to include:
- In the architecture document when there are multiple deployable units
- In feature plan.md when the feature spans containers

---

### C4 Component Diagram
Shows the internal structure of one container — classes, modules, interfaces.

```mermaid
C4Component
    title Component Diagram — [Container Name]
    Container_Boundary(c, "[Container Name]") {
        Component(router, "Router", "FastAPI", "HTTP routing and auth")
        Component(service, "Service Layer", "Python", "Business logic")
        Component(repo, "Repository", "Python", "Data access abstraction")
    }
    ContainerDb(db, "Database", "PostgreSQL", "")
    Rel(router, service, "Calls")
    Rel(service, repo, "Uses")
    Rel(repo, db, "Queries", "SQL")
```

When to include:
- In feature plan.md when the feature's internal structure needs clarifying
- Only when a container has ≥3 distinct internal components

---

### Sequence Diagram
Shows interactions between actors/services in time order.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant API as API Gateway
    participant Service
    participant DB as Database
    participant Cache

    User->>API: POST /resource (payload)
    API->>Service: validate + process(payload)

    Service->>Cache: get(key)
    alt Cache hit
        Cache-->>Service: cached result
    else Cache miss
        Service->>DB: SELECT ...
        DB-->>Service: rows
        Service->>Cache: set(key, result, ttl)
    end

    Service-->>API: result
    API-->>User: 200 OK (response)
```

Rules for good sequence diagrams:
- Use `autonumber` for every diagram
- Use `alt`/`else`/`opt` to show conditional flows — don't flatten them
- Show both happy path AND error/alternative paths
- Name participants clearly (avoid generic "Service1", "Service2")
- Add a `Note` for important side effects or constraints

---

### State Diagram
Shows how an entity transitions between states in response to events.

```mermaid
stateDiagram-v2
    [*] --> Draft : create

    Draft --> UnderReview : submit
    Draft --> Cancelled : cancel

    UnderReview --> Approved : approve
    UnderReview --> Rejected : reject
    UnderReview --> Draft : request changes

    Approved --> Published : publish
    Approved --> Cancelled : cancel

    Published --> Archived : archive
    Cancelled --> [*]
    Archived --> [*]

    note right of UnderReview
        SLA: 5 business days
    end note
```

When to include:
- When an entity has a lifecycle (orders, approvals, workflows, tasks)
- In feature plan.md when the feature changes how an entity transitions

---

### Entity Relationship Diagram (ERD)
Shows data entities and the relationships between them.

```mermaid
erDiagram
    USER {
        uuid id PK
        string email UK
        string name
        timestamp created_at
    }

    PROJECT {
        uuid id PK
        string name
        uuid owner_id FK
        timestamp created_at
    }

    TASK {
        uuid id PK
        string title
        string status
        uuid project_id FK
        uuid assignee_id FK
        timestamp due_date
    }

    USER ||--o{ PROJECT : owns
    PROJECT ||--o{ TASK : contains
    USER ||--o{ TASK : "assigned to"
```

Rules for good ERDs:
- Mark PK, FK, UK explicitly
- Show cardinality (`||--o{`, `||--|{`, `}o--o{`)
- Include only the entities relevant to the feature or system
- Show at least the key non-relational fields (not just IDs)

---

### Deployment Diagram
Shows where components run — hosts, containers, cloud regions, network zones.

```mermaid
graph TB
    subgraph "Internet"
        User["👤 User"]
    end

    subgraph "Azure — UK South"
        subgraph "App Service Plan"
            API["FastAPI App\n(Python 3.13)"]
        end

        subgraph "Private VNet"
            Worker["Background Worker\n(Python)"]
            DB["Azure PostgreSQL\nFlexible Server"]
            Cache["Azure Cache\nfor Redis"]
        end

        subgraph "Azure DevOps"
            CI["Build Pipeline"]
        end
    end

    subgraph "External"
        Fabric["Microsoft Fabric\nSemantic Model"]
    end

    User -->|HTTPS| API
    API --> Worker
    Worker --> DB
    Worker --> Cache
    Worker -->|REST API| Fabric
    CI -->|deploy| API
    CI -->|deploy| Worker
```

When to include:
- In the architecture document when deployment topology is non-trivial
- When security boundaries, network zones, or data residency matter

---

### Flowchart (directed graph)
Shows process flow, decision trees, or task dependencies.

```mermaid
graph TD
    A[Start] --> B{Condition?}
    B -->|Yes| C[Action A]
    B -->|No| D[Action B]
    C --> E[Shared step]
    D --> E
    E --> F[End]
```

Prefer `flowchart TD` over `graph TD` for process flows — identical syntax, clearer intent.
Use sequence diagrams instead when the flow involves multiple actors interacting over time.

---

## Step 2: Produce the diagrams

For each selected diagram:
1. Confirm the diagram type and what it will show
2. Generate the Mermaid source with realistic, named entities
3. Add a one-sentence caption explaining what the diagram reveals

---

## Step 3: Save and wire in

**For a new feature spec:**
- Add diagrams to `specs/[feature]/plan.md` (Spec Kit's `/speckit-plan` output)

**For the architecture document:**
- Add or update diagrams in `project-management/Background/01-final-architecture-document.md`

**For a standalone analysis:**
- Save to `project-management/Work/analysis/diagrams-[topic].md`

---

## Quality rules

- Every diagram must have a `title` or caption
- Sequence diagrams must use `autonumber`
- ERDs must mark PK/FK/UK
- C4 diagrams must use C4Context/C4Container/C4Component keywords (not plain flowcharts)
- No more than 12–15 nodes per diagram — split into multiple diagrams if larger
- Only include a diagram if it reveals something that prose cannot
