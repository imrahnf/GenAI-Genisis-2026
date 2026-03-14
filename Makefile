build-sandboxes:
\t@for d in sandboxes/*/ ; do \\\n\t  name=$$(basename $$d) ; \\\n\t  echo \"Building demoforge/$$name:latest from $$d\" ; \\\n\t  docker build -t demoforge/$$name:latest $$d ; \\\n\tdone\n+
