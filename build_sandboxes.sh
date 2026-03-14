for d in sandboxes/*/; do
  name="$(basename "$d")"
  echo "Building demoforge/$name:latest ..."
  docker build -t "demoforge/$name:latest" "$d"
done
echo "Done. Images: $(docker images --format '{{.Repository}}:{{.Tag}}' demoforge/* 2>/dev/null || true)"