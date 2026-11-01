# GPU lock for the one shared GTX 1660 (team rule): the lock is a directory made with mkdir, and owner.txt in it says
# who holds it. Take it before ANY render (test renders too), hold it for one render, release it right after.
#   source scripts/gpu_lock.sh
#   gpu_lock_acquire <your-name> "<what>"   # waits, checking every 30 s, while someone else holds it
#   ...render...
#   gpu_lock_release
GPU_LOCK=/c/Users/Chris/TribeUE/gpu.lock.d

gpu_lock_acquire() {
  local who="$1" what="${2:-render}"
  until mkdir "$GPU_LOCK" 2>/dev/null; do
    echo "[gpu] busy: $(cat "$GPU_LOCK/owner.txt" 2>/dev/null || echo 'no owner.txt yet'); next check in 30 s"
    sleep 30
  done
  echo "$who $(date '+%Y-%m-%d %H:%M:%S') $what" > "$GPU_LOCK/owner.txt"
  echo "[gpu] acquired: $who, $what"
}

gpu_lock_release() {
  rm -f "$GPU_LOCK/owner.txt"
  rmdir "$GPU_LOCK" 2>/dev/null && echo "[gpu] released"
}
