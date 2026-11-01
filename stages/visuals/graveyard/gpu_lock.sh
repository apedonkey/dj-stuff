# GPU lock for the one shared GTX 1660 (team rule; the Halloween lead's protocol): the lock is the directory
# C:/Users/Chris/TribeUE/gpu.lock.d made with mkdir (atomic); owner.txt inside says who holds it. Take it before ANY
# Blender render (test renders too), hold it for one loop render, remove it right after, also on failure.
#   source scripts/gpu_lock.sh
#   gpu_lock_acquire "<loop>"    # polls every 10 s while someone else holds it
#   ...render...
#   gpu_lock_release             # removes the lock only if this shell took it
GPU_LOCK=/c/Users/Chris/TribeUE/gpu.lock.d
GPU_LOCK_HELD=0

gpu_lock_acquire() {
  local what="$1" waited=0
  until mkdir "$GPU_LOCK" 2>/dev/null; do
    if [ $((waited % 120)) -eq 0 ]; then
      echo "[gpu] busy: $(cat "$GPU_LOCK/owner.txt" 2>/dev/null || echo 'no owner.txt yet')"
    fi
    sleep 10
    waited=$((waited + 10))
  done
  GPU_LOCK_HELD=1
  echo "halloween visuals: $what ($(date '+%Y-%m-%d %H:%M:%S'))" > "$GPU_LOCK/owner.txt"
  echo "[gpu] acquired after ${waited} s: $what"
}

gpu_lock_release() {
  if [ "$GPU_LOCK_HELD" = "1" ]; then
    rm -rf "$GPU_LOCK"
    GPU_LOCK_HELD=0
    echo "[gpu] released"
  fi
}
