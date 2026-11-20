#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

branch=feat/backend-base-datos
if [[ $(git branch --show-current) != "$branch" ]]; then
    echo "Run this from the $branch branch." >&2
    exit 1
fi
if [[ -n $(git status --porcelain) ]]; then
    echo "Commit or remove local changes before publication." >&2
    exit 1
fi

python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r db/requirements.txt

if [[ -z ${TEST_DATABASE_URL:-} ]]; then
    if ! docker info >/dev/null 2>&1; then
        echo "Docker is unavailable. Set TEST_DATABASE_URL to an isolated PostgreSQL database." >&2
        exit 1
    fi
    container="ecoconecta-test-$(python -c 'import secrets; print(secrets.token_hex(6))')"
    password=$(python -c 'import secrets; print(secrets.token_hex(16))')
    docker run --rm -d --name "$container" \
        -e POSTGRES_PASSWORD="$password" -e POSTGRES_DB=ecoconecta_test \
        -p 127.0.0.1::5432 postgres:16-alpine >/dev/null
    trap 'docker rm -f "$container" >/dev/null 2>&1 || true' EXIT
    port=$(docker port "$container" 5432/tcp | awk -F: '{print $NF}')
    export TEST_DATABASE_URL="postgresql://postgres:${password}@127.0.0.1:${port}/ecoconecta_test"
    ready=false
    for _ in {1..30}; do
        if docker exec "$container" pg_isready -U postgres -d ecoconecta_test >/dev/null 2>&1; then
            ready=true
            break
        fi
        sleep 1
    done
    if [[ $ready != true ]]; then
        echo "PostgreSQL did not become ready." >&2
        exit 1
    fi
fi

python -m unittest discover -s db/tests -v
git diff "$(git merge-base origin/main HEAD)" HEAD --check
git push -u origin "$branch"

local_sha=$(git rev-parse HEAD)
remote_sha=$(git ls-remote origin "refs/heads/$branch" | awk '{print $1}')
if [[ $remote_sha != "$local_sha" ]]; then
    echo "Remote SHA does not match local HEAD." >&2
    exit 1
fi
echo "Published $branch at $remote_sha"
