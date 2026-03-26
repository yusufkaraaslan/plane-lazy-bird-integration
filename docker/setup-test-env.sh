#!/usr/bin/env bash
# setup-test-env.sh — Clone and patch Plane for local integration testing.
#
# This script:
#   1. Clones makeplane/plane (if not already present)
#   2. Patches Plane's Django settings to add plane_lazy_bird to INSTALLED_APPS
#   3. Adds our URL route to Plane's URL config
#   4. pip-installs our package into Plane's environment
#   5. Runs all migrations (Plane + plane_lazy_bird)
#   6. Creates test workspace, project, states, and API key via Django shell
#
# Usage:
#   ./docker/setup-test-env.sh [plane-dir]
#
# Arguments:
#   plane-dir   Directory to clone Plane into (default: ./plane-dev)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLANE_DIR="${1:-$PROJECT_ROOT/plane-dev}"
PLANE_REPO="https://github.com/makeplane/plane.git"
PLANE_BRANCH="master"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Step 1: Clone Plane ──────────────────────────────────────────────────────

if [ -d "$PLANE_DIR" ]; then
    info "Plane directory already exists at $PLANE_DIR, skipping clone."
else
    info "Cloning Plane from $PLANE_REPO into $PLANE_DIR..."
    git clone --depth 1 --branch "$PLANE_BRANCH" "$PLANE_REPO" "$PLANE_DIR"
    info "Clone complete."
fi

# ── Step 2: Patch Plane settings ─────────────────────────────────────────────

# Find the settings file to patch (common.py is shared across all environments)
SETTINGS_CANDIDATES=(
    "$PLANE_DIR/apiserver/plane/settings/common.py"
    "$PLANE_DIR/apiserver/plane/settings/production.py"
    "$PLANE_DIR/apiserver/plane/settings/local.py"
)

SETTINGS_FILE=""
for candidate in "${SETTINGS_CANDIDATES[@]}"; do
    if [ -f "$candidate" ]; then
        SETTINGS_FILE="$candidate"
        break
    fi
done

if [ -z "$SETTINGS_FILE" ]; then
    error "Could not find Plane settings file. Searched:"
    for candidate in "${SETTINGS_CANDIDATES[@]}"; do
        error "  $candidate"
    done
    exit 1
fi

PATCH_MARKER="# --- plane_lazy_bird integration patch ---"

if grep -q "$PATCH_MARKER" "$SETTINGS_FILE" 2>/dev/null; then
    info "Settings already patched in $SETTINGS_FILE, skipping."
else
    info "Patching $SETTINGS_FILE to add plane_lazy_bird..."
    cat >> "$SETTINGS_FILE" << 'SETTINGS_PATCH'

# --- plane_lazy_bird integration patch ---
import os
INSTALLED_APPS += ["plane_lazy_bird"]

LAZY_BIRD_API_URL = os.environ.get("LAZY_BIRD_API_URL", "http://localhost:9000")
LAZY_BIRD_API_KEY = os.environ.get("LAZY_BIRD_API_KEY", "lb_test_integration_key")
LAZY_BIRD_WEBHOOK_SECRET = os.environ.get("LAZY_BIRD_WEBHOOK_SECRET", "whsec_test_integration_secret_min16")
# --- end plane_lazy_bird patch ---
SETTINGS_PATCH
    info "Settings patched."
fi

# ── Step 3: Patch Plane URL config ───────────────────────────────────────────

URLS_FILE="$PLANE_DIR/apiserver/plane/urls.py"
URL_PATCH_MARKER="# --- plane_lazy_bird URL patch ---"

if [ ! -f "$URLS_FILE" ]; then
    # Try alternative locations
    URLS_FILE="$PLANE_DIR/apiserver/plane/app/urls/root.py"
fi

if [ -f "$URLS_FILE" ]; then
    if grep -q "$URL_PATCH_MARKER" "$URLS_FILE" 2>/dev/null; then
        info "URL config already patched in $URLS_FILE, skipping."
    else
        info "Patching $URLS_FILE to include plane_lazy_bird URLs..."
        cat >> "$URLS_FILE" << 'URL_PATCH'

# --- plane_lazy_bird URL patch ---
from django.urls import include as _lb_include
urlpatterns += [_lb_include("plane_lazy_bird.urls")]
# --- end plane_lazy_bird URL patch ---
URL_PATCH
        info "URL config patched."
    fi
else
    warn "Could not find Plane URL config. You may need to manually add:"
    warn "  path('', include('plane_lazy_bird.urls'))"
fi

# ── Step 4: Install our package ──────────────────────────────────────────────

info "Installing plane-lazy-bird-integration package..."
cd "$PLANE_DIR/apiserver"

# Create venv if not exists
if [ ! -d "venv" ] && [ -z "${VIRTUAL_ENV:-}" ]; then
    info "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

pip install -e "$PROJECT_ROOT" 2>&1 | tail -3
info "Package installed."

# ── Step 5: Run migrations ───────────────────────────────────────────────────

info "Running database migrations..."

# Set up minimal env vars if not already set
export DATABASE_URL="${DATABASE_URL:-postgres://plane:plane@localhost:5432/plane}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379}"
export SECRET_KEY="${SECRET_KEY:-test-secret-key-not-for-production}"

python manage.py migrate --noinput 2>&1 | tail -5
info "Migrations complete."

# ── Step 6: Create test data ─────────────────────────────────────────────────

info "Creating test workspace, project, states, and API key..."

python manage.py shell -c "
import os, sys

try:
    from plane.db.models import Workspace, Project, State, APIToken
    from django.contrib.auth import get_user_model

    User = get_user_model()

    # Create test user
    user, created = User.objects.get_or_create(
        email='test@lazybird.dev',
        defaults={'username': 'lazybird-test', 'is_active': True}
    )
    if created:
        user.set_password('testpassword123')
        user.save()
        print(f'Created test user: {user.email}')
    else:
        print(f'Test user already exists: {user.email}')

    # Create workspace
    workspace, created = Workspace.objects.get_or_create(
        slug='lazy-bird-test',
        defaults={
            'name': 'Lazy Bird Test Workspace',
            'owner': user,
        }
    )
    status = 'Created' if created else 'Already exists'
    print(f'{status} workspace: {workspace.slug} (id={workspace.id})')

    # Create project
    project, created = Project.objects.get_or_create(
        workspace=workspace,
        name='Integration Test Project',
        defaults={
            'identifier': 'LBT',
            'created_by': user,
        }
    )
    status = 'Created' if created else 'Already exists'
    print(f'{status} project: {project.name} (id={project.id})')

    # Create states
    for state_name, color in [('Ready', '#f59e0b'), ('In Progress', '#3b82f6'), ('In Review', '#8b5cf6'), ('Done', '#22c55e')]:
        state, created = State.objects.get_or_create(
            project=project,
            name=state_name,
            defaults={
                'color': color,
                'workspace': workspace,
                'created_by': user,
            }
        )
        status = 'Created' if created else 'Already exists'
        print(f'{status} state: {state.name} (id={state.id})')

    # Create API token
    try:
        token, created = APIToken.objects.get_or_create(
            user=user,
            workspace=workspace,
            defaults={'label': 'lazy-bird-test-token'}
        )
        if created:
            print(f'Created API token: {token.token}')
        else:
            print(f'API token already exists')
    except Exception as e:
        print(f'Could not create API token (model may differ): {e}')

    print()
    print('=== Test Environment Ready ===')
    print(f'Workspace ID: {workspace.id}')
    print(f'Project ID:   {project.id}')
    print(f'User email:   {user.email}')

except ImportError as e:
    print(f'WARNING: Could not import Plane models: {e}')
    print('This is expected if running outside a full Plane environment.')
    print('The package is installed — test data will be created when Plane DB is available.')
    sys.exit(0)
except Exception as e:
    print(f'WARNING: Could not create test data: {e}')
    print('The package is installed — run this script again once the database is ready.')
    sys.exit(0)
" 2>&1

info "Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Start Plane:  cd $PLANE_DIR && docker compose up"
echo "  2. Run integration tests:  pytest tests/integration/ -v"
echo ""
