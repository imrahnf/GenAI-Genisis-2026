for d in sandboxes/*/; do
  name="$(basename "$d")"             # preset, bank, etc.
  docker build -t "demoforge/$name:latest" "$d"
done