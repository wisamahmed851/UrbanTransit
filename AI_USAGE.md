# AI Usage Declaration

All AI assistance used in UrbanTransit IQ is declared here. Each instruction given to the
AI assistant is also logged verbatim in [documentation/COMMAND_LOG.md](documentation/COMMAND_LOG.md).

| # | Tool | Purpose | Type of help | Files affected | Modifications made | Testing completed | Verifying team member |
|---|---|---|---|---|---|---|---|
| 1 | Claude Code (Claude Opus 5.5) | Phase 0 project setup | Environment detection, WSL2/Hadoop/MySQL installation and debugging, repo scaffolding, documentation templates, `.gitignore`, requirements pinning, config files, verification scripts, installation steps | `.gitignore`, `.gitattributes`, `README.md`, `AI_USAGE.md`, `DEV_LOG.md`, `LICENSE`, `requirements.txt`, `.env.example`, `config/*`, `hdfs_scripts/*` (incl. `conf/*.xml`, `setup_hadoop.sh`), `spark_jobs/verify_spark.py`, `database/verify_mysql.py`, `src/app.py`, `documentation/COMMAND_LOG.md` | Initial creation (Phase 0) | Phase 0 completion checklist run 2026-09-24: 12/12 PASS (verify_hdfs, verify_spark incl. Spark SQL/Parquet/HDFS read, verify_mysql, Flask /health 200); see DEV_LOG.md | _To be filled by team_ |
