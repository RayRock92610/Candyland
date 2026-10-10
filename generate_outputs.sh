#!/bin/bash
echo "=== Rockberrypie ==="
cd /app/rockberrypie
git log -n 3 --oneline
echo
git diff HEAD~1..HEAD --stat

echo -e "\n=== Rockflow ==="
cd /app/Rockflow
git log -n 3 --oneline
echo
git diff HEAD~1..HEAD --stat

echo -e "\n=== Candyland ==="
cd /app
git log -n 3 --oneline
# In Candyland, because we re-checked out the code and merged PRs locally, the history is just the root commit and our cleanup.
# To show what was added in our PR 76/77 reconciliation, we would normally diff against main, but main is now our HEAD.
# We will just show the recent commits.
