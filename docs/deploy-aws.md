# Running a demo on AWS

The stack is built to be stood up for a demo and destroyed afterwards. Day-to-day work happens on `docker compose` for nothing.

## What it costs

| | Approx. |
|---|---|
| Left running for a month | ~$75 (ALB ~$16, RDS ~$14, ElastiCache ~$12, the two Fargate tasks ~$20, public IPv4 ~$15) |
| A two-hour demo, then destroyed | well under $1 |
| Torn down | $0 for the stack. The state bucket and budget alarm stay, and cost cents at most. |

There is deliberately no NAT gateway (about $32 a month per AZ). Tasks run in public subnets with a public IP for outbound access, and security groups keep inbound locked down. Prices are rough `us-east-1` on-demand figures, check the AWS pricing pages before relying on them.

## Runbook

Commands run from `infra/`. [infra/README.md](../infra/README.md) has the detail behind each step, and the manual equivalent of what CI does.

**Once per account**

1. Set the budget alarm (`budget/`). It emails if a teardown is forgotten. Do this before anything else.
2. Create the state bucket and the GitHub OIDC roles (`ci/`), then copy their three outputs into repo variables.

**Stand it up** (10 to 15 minutes, almost all of it RDS and ElastiCache)

3. Set the `DEPLOY_ENABLED` repo variable to `true` and run the `deploy` workflow from the Actions tab. It creates the stack, pushes both images, runs the migrations and smoke tests the api.

**Seed it and demo**

4. The database starts empty, so create the demo account and an analyzed portfolio:

   ```bash
   API_URL=$(terraform output -raw api_url)
   cd ../backend && python -m scripts.seed --api-url "$API_URL"
   ```

   It waits for the worker to finish and prints the login. Set `QUANTLY_DEMO_PASSWORD` first for anything other than the well-known default.
5. Point the local frontend at the stack and sign in:

   ```bash
   cd ../frontend && VITE_API_URL=$API_URL npm run dev
   ```

**Tear it down**

6. Set `DEPLOY_ENABLED` back to `false`, so the next push to `main` does not rebuild the stack.
7. Destroy it. This is the only real off switch: the ALB and ElastiCache cannot be stopped, only deleted, and a stopped RDS instance restarts itself after 7 days.

   ```bash
   terraform destroy -var-file=environments/dev.tfvars
   terraform state list   # prints nothing when it is all gone
   ```
