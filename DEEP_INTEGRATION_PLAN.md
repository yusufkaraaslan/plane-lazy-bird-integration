# Deep Integration Plan: Lazy-Bird in Plane UI

## Goal
Everything managed from within Plane's interface - no external dashboards needed.

## Architecture

### Backend (Django Package - This Repo)
```
plane_lazy_bird/
├── models.py              # AutomationConfig, TaskRunMapping
├── signals.py             # Auto-queue on state change
├── webhooks.py            # Receive Lazy-Bird events
├── client.py              # Lazy-Bird API client
├── api.py                 # ⭐ NEW: REST API endpoints
├── serializers.py         # ⭐ NEW: DRF serializers
├── urls.py                # ⭐ UPDATED: Add API routes
├── admin.py               # Django admin (fallback)
└── management/commands/
```

### Frontend (React Components)
```
plane_lazy_bird/frontend/
├── components/
│   ├── LazyBirdTaskPanel.tsx      # Issue sidebar panel
│   ├── LazyBirdSettings.tsx       # Project settings page
│   ├── TaskStatusBadge.tsx        # Status indicator
│   ├── TaskLogsModal.tsx          # View logs popup
│   └── TriggerTaskButton.tsx      # Manual trigger
├── hooks/
│   ├── useLazyBirdTasks.ts        # Fetch tasks for issue
│   ├── useLazyBirdConfig.ts       # Manage config
│   └── useTriggerTask.ts          # Trigger mutation
├── api/
│   └── lazy-bird.ts               # API client
└── types/
    └── lazy-bird.ts               # TypeScript types
```

### Integration Points in Plane

**1. Issue Detail Sidebar**
```typescript
// web/components/issues/issue-detail/sidebar.tsx
import { LazyBirdTaskPanel } from '@/plane_lazy_bird/components/LazyBirdTaskPanel';

export const IssueDetailSidebar = () => {
  return (
    <>
      {/* Existing Plane sidebar sections */}
      <LazyBirdTaskPanel issueId={issue.id} />
    </>
  );
};
```

**2. Project Settings**
```typescript
// web/components/project/settings/integrations.tsx
import { LazyBirdSettings } from '@/plane_lazy_bird/components/LazyBirdSettings';

export const ProjectIntegrations = () => {
  return (
    <>
      {/* Other integrations */}
      <LazyBirdSettings projectId={project.id} />
    </>
  );
};
```

**3. Issue List (Task Status Badge)**
```typescript
// web/components/issues/issue-list-item.tsx
import { TaskStatusBadge } from '@/plane_lazy_bird/components/TaskStatusBadge';

export const IssueListItem = ({ issue }) => {
  return (
    <div className="issue-row">
      {/* Existing issue info */}
      <TaskStatusBadge issueId={issue.id} />
    </div>
  );
};
```

## REST API Endpoints

### Configuration Endpoints
```
GET    /api/lazy-bird/config/{project_id}/          # Get config
POST   /api/lazy-bird/config/{project_id}/          # Create/update config
POST   /api/lazy-bird/config/test-connection/       # Test API connection
```

### Task Endpoints
```
GET    /api/lazy-bird/issues/{issue_id}/tasks/      # List all tasks
POST   /api/lazy-bird/issues/{issue_id}/tasks/trigger/  # Trigger new task
GET    /api/lazy-bird/issues/{issue_id}/tasks/{task_id}/logs/  # Get logs
POST   /api/lazy-bird/issues/{issue_id}/tasks/{task_id}/cancel/  # Cancel task
GET    /api/lazy-bird/issues/{issue_id}/tasks/{task_id}/status/  # Get status
```

### Webhook Endpoint
```
POST   /webhooks/lazy-bird/                         # Receive Lazy-Bird events
```

## User Experience Flow

### 1. Initial Setup (in Plane Settings)
```
User → Project Settings → Integrations → Lazy-Bird
1. Enter Lazy-Bird API URL
2. Enter API Key
3. Click "Test Connection" ✓
4. Enable "Auto-trigger on Ready"
5. Configure state mapping
6. Save
```

### 2. Viewing Task Status (in Issue Detail)
```
User → Opens Issue #123 → Sidebar shows:

┌─────────────────────────┐
│ Lazy-Bird Automation    │
├─────────────────────────┤
│ ● Running               │
│ Task #task-abc123       │
│ Started: 2 mins ago     │
│                         │
│ [View Logs] [Cancel]    │
└─────────────────────────┘
```

### 3. Manual Trigger (in Issue Detail)
```
User → Issue #456 → Click "Trigger Lazy-Bird Task"
→ Modal: "What should the task do?"
→ Enter description
→ Click "Start Task"
→ Task appears in sidebar
```

### 4. Task Completion (Automatic Update)
```
Lazy-Bird completes task
→ Webhook fires
→ Issue state changes to "In Review"
→ Comment added: "✓ Task completed! PR: #123"
→ Sidebar updates:

┌─────────────────────────┐
│ Lazy-Bird Automation    │
├─────────────────────────┤
│ ✓ Success               │
│ Task #task-abc123       │
│ Completed: 5 mins ago   │
│                         │
│ PR: #123                │
│ [View Logs]             │
└─────────────────────────┘
```

## Implementation Strategy

### Phase 1: Backend API (This Repo)
**Files to create:**
- `plane_lazy_bird/api.py` - ViewSets for config and tasks
- `plane_lazy_bird/serializers.py` - DRF serializers
- `plane_lazy_bird/permissions.py` - API permissions
- Update `plane_lazy_bird/urls.py` - Add API routes

**Tests:**
- `tests/test_api.py` - API endpoint tests
- Mock Plane's authentication

### Phase 2: Frontend Components (This Repo or Separate Package)

**Option A: Include in Django Package**
```
plane_lazy_bird/
├── frontend/          # React components
│   ├── package.json
│   ├── tsconfig.json
│   └── src/
└── static/
    └── lazy_bird/     # Built assets
```

**Option B: Separate NPM Package**
```
@plane-lazy-bird/react-components
→ Published to npm
→ Plane installs it
```

### Phase 3: Plane Integration

**Option A: Contribute to Plane (PR)**
- Fork Plane
- Add integration points for Lazy-Bird components
- Submit PR to Plane maintainers
- If accepted, deep integration works out-of-the-box

**Option B: Maintain Custom Plane Fork**
- Fork Plane
- Add Lazy-Bird components
- Maintain fork with regular Plane updates
- Users install your fork instead of vanilla Plane

**Option C: Plane Plugin System (If Available)**
- Check if Plane has plugin architecture
- Register components via plugin manifest
- No fork needed

## Development Workflow

### 1. Develop Backend API
```bash
cd plane-lazy-bird-integration
poetry install

# Create API files
touch plane_lazy_bird/api.py
touch plane_lazy_bird/serializers.py

# Write tests
pytest tests/test_api.py

# Test with mock Plane
python manage.py runserver
```

### 2. Develop Frontend Components
```bash
cd plane-lazy-bird-integration/frontend
npm install

# Develop components
npm run dev

# Build for production
npm run build
# → Output to plane_lazy_bird/static/lazy_bird/
```

### 3. Test Integration with Plane
```bash
# Clone Plane
git clone https://github.com/makeplane/plane.git plane-dev
cd plane-dev

# Install your package
pip install -e /path/to/plane-lazy-bird-integration

# Add to Plane's INSTALLED_APPS
# Import components in Plane's frontend
# Run Plane
docker-compose up
```

## Questions to Answer

1. **Does Plane have a plugin system?**
   - Need to examine Plane's codebase
   - Check their docs for extension points

2. **Where should frontend code live?**
   - In this Django package?
   - Separate npm package?
   - Directly in Plane fork?

3. **Distribution strategy?**
   - Pure package (users modify Plane themselves)?
   - Fork of Plane (all-in-one)?
   - Both?

## Next Steps

1. Examine Plane's architecture for plugin support
2. Design REST API endpoints
3. Create React component wireframes
4. Decide on distribution strategy
5. Implement backend API
6. Implement frontend components
7. Test integration
8. Document installation for users
