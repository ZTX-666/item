# Defect Tracker

A modular full-stack system for managing manufacturing quality defects, safety incidents, and operational workflows — with structured lifecycle control, database-driven role-based access, and full audit history.

Built with **FastAPI**, **SQLAlchemy**, **PostgreSQL**, **React**, and **TypeScript**.

---

## Why This Project Exists

I spent four years as a Quality Representative on the Cummins X15 heavy-duty diesel engine line, and a lot of that work was tracking defects, opening containments, and chasing corrective actions through tools that were either too rigid for real shop-floor reality or too loose to enforce the rules that matter.

This project is what a defect and safety system would look like if it were designed by someone who had to live with it on the floor: opinionated about workflow integrity, paranoid about audit history, and built so that the same business rules hold no matter where the request comes from.

---

## Architecture

| Layer | Technology |
| ------- | | ------------|  
| Frontend | React + TypeScript + Vite |
| API | FastAPI |
| ORM | SQLAlchemy |
| Database | PostgreSQL |
| Auth | OAuth2 + JWT |
| Authorization | Database-driven RBAC (Users → Roles → Scopes) |
| Workflow | Enum-backed state machines |
| Pattern | Service layer (routers → services → models) |
| Audit | Lifecycle transition logging |
| Container | Docker Compose |

The system separates HTTP concerns from business logic using a service layer to enforce domain rules and workflow integrity.

---

## Quick Start

```bash
git clone https://github.com/tlongmx4/Defect-Tracker.git
cd Defect-Tracker

# Start backend
docker compose up --build

# In another terminal, start frontend
cd frontend
npm install
npm run dev
```

The API will be available at `http://localhost:8000`, with interactive Swagger docs at `http://localhost:8000/docs`.  
The frontend will run at `http://localhost:5173`.

---

## Modules

### Quality Module — Defects

- Create and manage manufacturing defects
- Status tracking with filtering and pagination
- Scope-based access control (`quality:defects:read` / `quality:defects:write`)

### Safety Module — Incidents (v2)

Structured safety incident tracking with enforced workflow rules.

**Incident attributes:**

- Severity: `NEAR_MISS`, `FIRST_AID`, `RECORDABLE`, `PSIF`
- Location, Department, Shift, Description

**Controlled state transitions:**

```text
OPEN → INVESTIGATING → CORRECTIVE_ACTION → CLOSED
```

**Enforced business rules:**

- Incidents cannot move to `CLOSED` without a documented corrective action
- Invalid transitions are rejected at the service layer before the database is touched

**Audit trail:**

- Every status change records old status, new status, user, and timestamp

**Scopes:** `safety:incidents:read`, `safety:incidents:write`

---

## Frontend

A modern React application providing a user interface for the defect tracking system.

**Tech Stack:**

- React 19 with TypeScript
- Vite for build tooling
- Tailwind CSS for styling
- TanStack React Query for data fetching
- shadcn/ui for component library
- React Router for navigation

**Features:**

- Type-safe API integration matching backend schemas
- Responsive UI components
- Form handling for defects and safety incidents
- Real-time status updates and audit trails

**Development:**

```bash
cd frontend
npm install
npm run dev  # Starts dev server on :5173
npm run build  # Production build
```

---

## Design Decisions

This project started as an exercise in mimicking real Cummins manufacturing quality processes in code. Working on the X15 line gave me a lot of opinions about how defect tracking, safety reporting, and authorization should work — and a lot of frustrations with how brittle most off-the-shelf tools are when business rules collide with reality. The choices below reflect that perspective.

### Service layer instead of fat routers

Routers in this project do exactly two things: validate the request shape and call into a service. All business rules — who can do what, which state transitions are legal, when an audit entry gets written — live in the service layer.

The reason is simple: in a real quality system, the same rule has to hold whether the action came from a web request, a scheduled job, or a CLI script. Putting the rules in the routers means duplicating them every time a new entry point shows up, and duplicated rules drift. Putting them in the service layer means there's one place a rule lives and one place it can be wrong.

### Database-driven RBAC instead of hardcoded role decorators

A lot of FastAPI tutorials show role checks as decorators with the role name baked in: `@requires_role("admin")`. That works until the day someone in the plant needs a permission their role doesn't have, and now you're shipping code to production to fix an org chart.

In manufacturing, roles and responsibilities shift constantly — a tech gets promoted, a supervisor takes on a new line, a quality engineer rotates departments. Storing roles and scopes in the database, with users mapped to roles and roles mapped to scopes, means access changes are configuration, not deployments. The route layer just asks "does this user have the `safety:incidents:write` scope?" and the answer comes from the data, not the code.

### Enum-backed state machines instead of a status string field

A defect or incident isn't really a record with a status column — it's a workflow with legal and illegal transitions. An incident in `OPEN` can move to `INVESTIGATING`, but it can't jump straight to `CLOSED`.

A "status" field as a free string lets any caller write any value, and the database happily stores nonsense. Modeling status as an enum and the transitions as an explicit map of allowed moves means the invalid states are unrepresentable — the service layer rejects the transition before it ever touches the database.

This is the same logic that lives inside real Cummins quality processes: a defect doesn't get closed without a documented containment and corrective action, and the system enforces that, not the person filling out the form.

### Business rules enforced at the service layer, not in the database

The incident module won't let you close an incident without a documented corrective action. That rule could live as a database constraint, but database constraints give you opaque errors and no good way to explain why the operation failed.

Enforcing it in the service layer means the API can return a clear, structured error that a frontend (or another service) can act on. The database is still the source of truth for what *is*; the service layer is the source of truth for what's *allowed*.

### Audit logging on every lifecycle transition

Every status change writes an audit row capturing the old status, the new status, the user who made the change, and the timestamp. This isn't a nice-to-have for a quality system — it's the entire point.

When something goes wrong on the floor, the question isn't "what's the current state of this defect," it's "who decided to close it, when, and what was the state before they touched it." Without that history, root cause analysis becomes guesswork. With it, the timeline is reconstructable.

Putting the audit write inside the same service method that performs the transition means there's no path where the state changes without an audit entry — they're atomic from the API's perspective.

### Separation of read and write scopes

Most people in a plant need to see defects and incidents — line techs, supervisors, engineers, leadership. Far fewer should be able to modify them.

Splitting `safety:incidents:read` from `safety:incidents:write` (and the same for the quality module) means the default safe answer for a new role is "give them read access," and write access is something you grant deliberately. It's a small thing, but it makes the principle of least privilege the path of least resistance instead of an extra step.

---

## Current Status

- ✅ Quality Module complete
- ✅ Safety Module complete (workflow + audit logging)
- ✅ RBAC fully implemented
- ✅ JWT authentication
- ✅ Dockerized for local development
- ✅ Frontend API integration and type safety
- ✅ React + TypeScript setup with modern tooling

## Roadmap

- Production / Downtime Tracking module
- Reporting and export features
- Analytics and dashboard layer
- Custom React components and UI
- Authentication integration in frontend
- Test suite (pytest) for service layer and state transitions

---

## License

MIT — see [LICENSE](./LICENSE).

Quality Module complete

Safety Module complete (workflow + audit logging)

RBAC fully implemented
